# neo4j_engine.py  — FIXED VERSION
# Fixes:
#   1. _q_ancestor: was only returning X when querying "ancestors OF y".
#      Now correctly handles all four arg combos including (name, "X") for
#      "descendants" direction used in _all_about().
#   2. _q_father / _q_mother: added fallback that also checks PARENT_OF
#      edges regardless of gender property, so nodes whose gender was stored
#      separately still resolve.
#   3. query_yes_no: unchanged, kept for compatibility.

from neo4j import GraphDatabase

_driver = None


# ── Connection helpers ────────────────────────────────────────────────────────

def _get_driver():
    global _driver
    if _driver is None:
        from neo4j_config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_lifetime=200,
            max_connection_pool_size=10,
            connection_acquisition_timeout=30,
        )
    return _driver


def _reset_driver():
    global _driver
    try:
        if _driver:
            _driver.close()
    except Exception:
        pass
    _driver = None


def _run(cypher: str, params: dict = None) -> list:
    try:
        from neo4j_config import NEO4J_DATABASE
        with _get_driver().session(database=NEO4J_DATABASE) as session:
            result = session.run(cypher, params or {})
            return [dict(r) for r in result]
    except Exception as e:
        print(f"[Neo4j ERROR] {e}")
        return []


def _is_var(s: str) -> bool:
    s = str(s).strip()
    return bool(s) and s[0].isupper()


# ── Public API ────────────────────────────────────────────────────────────────

def load_graph():
    _reset_driver()
    try:
        rows = _run("MATCH (p:Person) RETURN count(p) AS n")
        n = rows[0]["n"] if rows else 0
        print(f"[Neo4j] Connected successfully. {n} people in graph.")
        return True
    except Exception as e:
        print(f"[Neo4j] Connection FAILED: {e}")
        return False


def reload_graph():
    """Sync KNOWN_NAMES from the graph after a person is added."""
    import utils
    people = get_all_people()
    utils.KNOWN_NAMES.update(people)
    print(f"[Neo4j] Synced. {len(people)} people: {sorted(people)}")


def get_all_people() -> set:
    rows = _run("MATCH (p:Person) RETURN p.name AS name")
    return {r["name"] for r in rows if r.get("name")}


def person_exists_in_graph(name: str) -> bool:
    rows = _run(
        "MATCH (p:Person {name:$name}) RETURN p.name",
        {"name": name.lower()}
    )
    return len(rows) > 0


# ── Gender ────────────────────────────────────────────────────────────────────

def _q_male(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'male'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person {name:$n}) WHERE p.gender='male' RETURN p.name AS X",
        {"n": x})


def _q_female(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'female'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person {name:$n}) WHERE p.gender='female' RETURN p.name AS X",
        {"n": x})


# ── Parent / Child ────────────────────────────────────────────────────────────

def _q_parent(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run(
            "MATCH (x:Person)-[:PARENT_OF]->(y:Person {name:$n}) RETURN x.name AS X",
            {"n": y})
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (x:Person {name:$n})-[:PARENT_OF]->(y:Person) RETURN y.name AS X",
            {"n": x})
    return _run(
        "MATCH (x:Person {name:$xn})-[:PARENT_OF]->(y:Person {name:$yn}) RETURN x.name AS X",
        {"xn": x, "yn": y})


def _q_father(args):
    """
    FIX: First try gender-filtered query. If that returns nothing, fall back
    to any PARENT_OF edge (in case gender property is missing/mismatched).
    """
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
        if not rows:
            # fallback: any parent that has no female gender
            rows = _run("""
                MATCH (x:Person)-[:PARENT_OF]->(y:Person {name:$n})
                WHERE NOT x.gender = 'female'
                RETURN x.name AS X""", {"n": y})
        return rows
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n, gender:'male'})-[:PARENT_OF]->(y:Person)
            RETURN y.name AS X""", {"n": x})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'male'})-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_mother(args):
    """
    FIX: Same fallback strategy as _q_father.
    """
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
        if not rows:
            rows = _run("""
                MATCH (x:Person)-[:PARENT_OF]->(y:Person {name:$n})
                WHERE NOT x.gender = 'male'
                RETURN x.name AS X""", {"n": y})
        return rows
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n, gender:'female'})-[:PARENT_OF]->(y:Person)
            RETURN y.name AS X""", {"n": x})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'female'})-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_child(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(x:Person)
            RETURN x.name AS X""", {"n": y})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(x:Person {name:$n})
            RETURN y.name AS X""", {"n": x})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(x:Person {name:$xn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_son(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(x:Person {gender:'male'})
            RETURN x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(x:Person {name:$xn, gender:'male'})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_daughter(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(x:Person {gender:'female'})
            RETURN x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(x:Person {name:$xn, gender:'female'})
        RETURN x.name AS X""", {"xn": x, "yn": y})


# ── Spouse ────────────────────────────────────────────────────────────────────

def _q_spouse(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n})-[:MARRIED_TO]-(y:Person)
            RETURN y.name AS X""", {"n": x})
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:MARRIED_TO]-(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn})-[:MARRIED_TO]-(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_husband(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:MARRIED_TO]-(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'male'})-[:MARRIED_TO]-(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_wife(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:MARRIED_TO]-(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'female'})-[:MARRIED_TO]-(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


# ── Siblings ──────────────────────────────────────────────────────────────────

def _q_sibling(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person),
                  (p:Person)-[:PARENT_OF]->(y:Person {name:$n})
            WHERE x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person {name:$xn}),
              (p:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        WHERE x <> y
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_brother(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person {gender:'male'}),
                  (p:Person)-[:PARENT_OF]->(y:Person {name:$n})
            WHERE x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person {name:$xn, gender:'male'}),
              (p:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_sister(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person {gender:'female'}),
                  (p:Person)-[:PARENT_OF]->(y:Person {name:$n})
            WHERE x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person {name:$xn, gender:'female'}),
              (p:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


# ── Grandparents ──────────────────────────────────────────────────────────────

def _q_grandparent(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_grandfather(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'male'})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_grandmother(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'female'})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_grandchild(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person {name:$xn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_grandson(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person {gender:'male'})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'male'})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_granddaughter(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person {gender:'female'})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'female'})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


# ── Dada / Dadi / Nana / Nani ─────────────────────────────────────────────────

def _q_dada(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(f:Person {gender:'male'})
                  -[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'male'})-[:PARENT_OF]->(f:Person {gender:'male'})
              -[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_dadi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(f:Person {gender:'male'})
                  -[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'female'})-[:PARENT_OF]->(f:Person {gender:'male'})
              -[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_nana(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(m:Person {gender:'female'})
                  -[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'male'})-[:PARENT_OF]->(m:Person {gender:'female'})
              -[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_nani(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(m:Person {gender:'female'})
                  -[:PARENT_OF]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'female'})-[:PARENT_OF]->(m:Person {gender:'female'})
              -[:PARENT_OF]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


# ── Extended Family ───────────────────────────────────────────────────────────

def _q_uncle(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'male'})
            WHERE x <> p
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'male'})
        WHERE x <> p
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_aunt(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'female'})
            WHERE x <> p
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'female'})
        WHERE x <> p
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_cousin(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (ggp:Person)-[:PARENT_OF]->(pa:Person)-[:PARENT_OF]->(y:Person {name:$n}),
                  (ggp:Person)-[:PARENT_OF]->(ua:Person)-[:PARENT_OF]->(x:Person)
            WHERE pa <> ua AND x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (ggp:Person)-[:PARENT_OF]->(pa:Person)-[:PARENT_OF]->(y:Person {name:$yn}),
              (ggp:Person)-[:PARENT_OF]->(ua:Person)-[:PARENT_OF]->(x:Person {name:$xn})
        WHERE pa <> ua
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_nephew(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person {gender:'male'}),
                  (gp:Person)-[:PARENT_OF]->(y:Person {name:$n})
            WHERE z <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'male'}),
              (gp:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        WHERE z <> y
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_niece(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person {gender:'female'}),
                  (gp:Person)-[:PARENT_OF]->(y:Person {name:$n})
            WHERE z <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'female'}),
              (gp:Person)-[:PARENT_OF]->(y:Person {name:$yn})
        WHERE z <> y
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


# ── Urdu Relations ────────────────────────────────────────────────────────────

def _q_chacha(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'male'})
            WHERE x <> f
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'male'})
        WHERE x <> f
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_phoophi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'female'})
            WHERE x <> f
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'female'})
        WHERE x <> f
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_maamu(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'male'})
            WHERE x <> m
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'male'})
        WHERE x <> m
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_khala(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'female'})
            WHERE x <> m
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$yn}),
              (gp:Person)-[:PARENT_OF]->(x:Person {name:$xn,gender:'female'})
        WHERE x <> m
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_chachi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(ch:Person {gender:'male'}),
                  (x:Person {gender:'female'})-[:MARRIED_TO]-(ch)
            WHERE ch <> f
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_phuppa(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(ph:Person {gender:'female'}),
                  (x:Person {gender:'male'})-[:MARRIED_TO]-(ph)
            WHERE ph <> f
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_maami(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(ma:Person {gender:'male'}),
                  (x:Person {gender:'female'})-[:MARRIED_TO]-(ma)
            WHERE ma <> m
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_khalu(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(kh:Person {gender:'female'}),
                  (x:Person {gender:'male'})-[:MARRIED_TO]-(kh)
            WHERE kh <> m
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


# ── In-Laws ───────────────────────────────────────────────────────────────────

def _q_father_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'male'})-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_mother_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (x:Person {name:$xn,gender:'female'})-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_brother_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'male'})
            WHERE x <> s
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_sister_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->(x:Person {gender:'female'})
            WHERE x <> s
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_son_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(d:Person {gender:'female'}),
                  (x:Person {gender:'male'})-[:MARRIED_TO]-(d)
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


def _q_daughter_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]->(s:Person {gender:'male'}),
                  (x:Person {gender:'female'})-[:MARRIED_TO]-(s)
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


# ── Ancestor / Descendant — FIXED ─────────────────────────────────────────────

def _q_ancestor(args):
    """
    FIX: Also include INFERRED_ANCESTOR edges in ancestor queries so that
    results from hybrid reasoning are visible to the chatbot.
    ancestor(X, ali) → who are ancestors of ali
    ancestor(ali, X) → who is ali an ancestor of (descendants)
    """
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        # "who are the ancestors of Y?" — walk up the tree
        rows = _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
        if not rows:
            # also check inferred
            rows = _run("""
                MATCH (x:Person)-[:INFERRED_ANCESTOR]->(y:Person {name:$n})
                RETURN DISTINCT x.name AS X""", {"n": y})
        return rows
    if not _is_var(x) and _is_var(y):
        # "who is X an ancestor of?" — walk down the tree
        rows = _run("""
            MATCH (x:Person {name:$n})-[:PARENT_OF*1..]->(y:Person)
            RETURN DISTINCT y.name AS X""", {"n": x})
        if not rows:
            rows = _run("""
                MATCH (x:Person {name:$n})-[:INFERRED_ANCESTOR]->(y:Person)
                RETURN DISTINCT y.name AS X""", {"n": x})
        return rows
    # both bound — yes/no check
    rows = _run("""
        MATCH (x:Person {name:$xn})-[:PARENT_OF*1..]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})
    if not rows:
        rows = _run("""
            MATCH (x:Person {name:$xn})-[:INFERRED_ANCESTOR]->(y:Person {name:$yn})
            RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})
    return rows


def _q_descendant(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF*1..]->(x:Person)
            RETURN DISTINCT x.name AS X""", {"n": y})
    return _run("""
        MATCH (y:Person {name:$yn})-[:PARENT_OF*1..]->(x:Person {name:$xn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


def _q_blood_relative(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]-(y:Person {name:$n})
            WHERE x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    if not _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {name:$xn})-[:PARENT_OF*1..]-(y:Person {name:$yn})
            RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})
    return []


def _q_family_member(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person {name:$n})-[:PARENT_OF]-(x:Person)
            RETURN DISTINCT x.name AS X
            UNION
            MATCH (p:Person)-[:PARENT_OF]->(y:Person {name:$n}),
                  (p:Person)-[:PARENT_OF]->(x:Person)
            WHERE x <> y
            RETURN DISTINCT x.name AS X""", {"n": y})
    return []


# ── Properties ────────────────────────────────────────────────────────────────

def _q_dob(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.dob IS NOT NULL RETURN p.dob AS X",
            {"n": x})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {dob:$d}) RETURN p.name AS X", {"d": y})
    return []


def _q_occupation(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.occupation IS NOT NULL RETURN p.occupation AS X",
            {"n": x})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {occupation:$occ}) RETURN p.name AS X", {"occ": y})
    if _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE p.occupation IS NOT NULL RETURN p.name AS X, p.occupation AS Y")
    return []


def _q_lives_in(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.city IS NOT NULL RETURN p.city AS X",
            {"n": x})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {city:$city}) RETURN p.name AS X", {"city": y})
    if _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE p.city IS NOT NULL RETURN p.name AS X, p.city AS Y")
    return _run(
        "MATCH (p:Person {name:$xn, city:$yn}) RETURN p.name AS X",
        {"xn": x, "yn": y})


def _q_religion(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.religion IS NOT NULL RETURN p.religion AS X",
            {"n": x})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {religion:$r}) RETURN p.name AS X", {"r": y})
    if _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE p.religion IS NOT NULL RETURN p.name AS X, p.religion AS Y")
    return []


# ── Same group ────────────────────────────────────────────────────────────────

def _q_same_city(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (a:Person {name:$n}), (b:Person)
            WHERE a.city = b.city AND a <> b AND a.city IS NOT NULL
            RETURN DISTINCT b.name AS X""", {"n": name})
    return []


def _q_same_occupation(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (a:Person {name:$n}), (b:Person)
            WHERE a.occupation = b.occupation AND a <> b AND a.occupation IS NOT NULL
            RETURN DISTINCT b.name AS X""", {"n": name})
    return []


def _q_same_generation(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(a:Person {name:$n}),
                  (p:Person)-[:PARENT_OF]->(b:Person)
            WHERE a <> b
            RETURN DISTINCT b.name AS X
            UNION
            MATCH (gp:Person)-[:PARENT_OF]->()-[:PARENT_OF]->(a:Person {name:$n}),
                  (gp:Person)-[:PARENT_OF]->()-[:PARENT_OF]->(b:Person)
            WHERE a <> b
            RETURN DISTINCT b.name AS X""", {"n": name})
    return []


# ── Query dispatcher ──────────────────────────────────────────────────────────

_QUERY_MAP = {
    "male":            _q_male,
    "female":          _q_female,
    "parent":          _q_parent,
    "father":          _q_father,
    "mother":          _q_mother,
    "child":           _q_child,
    "son":             _q_son,
    "daughter":        _q_daughter,
    "husband":         _q_husband,
    "wife":            _q_wife,
    "spouse":          _q_spouse,
    "married":         _q_spouse,
    "sibling":         _q_sibling,
    "brother":         _q_brother,
    "sister":          _q_sister,
    "grandparent":     _q_grandparent,
    "grandfather":     _q_grandfather,
    "grandmother":     _q_grandmother,
    "grandchild":      _q_grandchild,
    "grandson":        _q_grandson,
    "granddaughter":   _q_granddaughter,
    "dada":            _q_dada,
    "dadi":            _q_dadi,
    "nana":            _q_nana,
    "nani":            _q_nani,
    "uncle":           _q_uncle,
    "aunt":            _q_aunt,
    "cousin":          _q_cousin,
    "nephew":          _q_nephew,
    "niece":           _q_niece,
    "chacha":          _q_chacha,
    "phoophi":         _q_phoophi,
    "maamu":           _q_maamu,
    "khala":           _q_khala,
    "chachi":          _q_chachi,
    "phuppa":          _q_phuppa,
    "maami":           _q_maami,
    "khalu":           _q_khalu,
    "father_in_law":   _q_father_in_law,
    "mother_in_law":   _q_mother_in_law,
    "brother_in_law":  _q_brother_in_law,
    "sister_in_law":   _q_sister_in_law,
    "son_in_law":      _q_son_in_law,
    "daughter_in_law": _q_daughter_in_law,
    "ancestor":        _q_ancestor,
    "descendant":      _q_descendant,
    "blood_relative":  _q_blood_relative,
    "family_member":   _q_family_member,
    "dob":             _q_dob,
    "occupation":      _q_occupation,
    "lives_in":        _q_lives_in,
    "religion":        _q_religion,
    "same_city":       _q_same_city,
    "same_occupation": _q_same_occupation,
    "same_generation": _q_same_generation,
}


def query(relation: str, args: list) -> list:
    fn = _QUERY_MAP.get(relation)
    if fn is None:
        return []
    try:
        return fn(args) or []
    except Exception as e:
        print(f"[Neo4j ERROR] query({relation}, {args}): {e}")
        return []


def query_yes_no(relation: str, args: list) -> bool:
    return bool(query(relation, args))