# neo4j_engine.py
# Assignment 3: All Prolog rules as Cypher graph queries.
# FIX: father/mother/son/daughter no longer require gender to be set
#      on nodes that were auto-created as stubs by graph_builder.py.
#      Gender is used when present; PARENT_OF direction is authoritative.

import time
from neo4j import GraphDatabase

_driver = None
_MAX_RETRIES = 3
_RETRY_DELAY = 2


def _get_driver():
    global _driver
    if _driver is None:
        from neo4j_config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_lifetime=200,
            max_connection_pool_size=10,
            connection_acquisition_timeout=60,
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
    from neo4j_config import NEO4J_DATABASE
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with _get_driver().session(database=NEO4J_DATABASE) as session:
                result = session.run(cypher, params or {})
                return [dict(r) for r in result]
        except Exception as e:
            last_error = e
            if attempt == _MAX_RETRIES:
                print(f"[Neo4j ERROR] {last_error}")
            else:
                _reset_driver()
                time.sleep(_RETRY_DELAY)
    return []


def _is_var(s: str) -> bool:
    s = str(s).strip()
    return bool(s) and s[0].isupper()


# ── Connection helpers ────────────────────────────────────────────────────────

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
    import utils
    people = get_all_people()
    utils.KNOWN_NAMES.update(people)
    print(f"[Neo4j] Synced. {len(people)} people: {sorted(people)}")


def get_all_people() -> set:
    rows = _run("MATCH (p:Person) RETURN p.name AS name")
    return {r["name"] for r in rows if r.get("name")}


def person_exists_in_graph(name: str) -> bool:
    name = str(name).lower().strip()
    if not name:
        return False
    rows = _run(
        "MATCH (p:Person) WHERE toLower(p.name) = $name RETURN p.name LIMIT 1",
        {"name": name}
    )
    return len(rows) > 0


# ── Gender (unary) ────────────────────────────────────────────────────────────

def _q_male(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'male'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.gender='male' RETURN p.name AS X",
        {"n": x.lower()})


def _q_female(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'female'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.gender='female' RETURN p.name AS X",
        {"n": x.lower()})


# ── Parent / Child ────────────────────────────────────────────────────────────

def _q_parent(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n
            RETURN x.name AS X""", {"n": y.lower()})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(x.name)=$n
            RETURN y.name AS X""", {"n": x.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_father(args):
    """
    FIX: Father = person who has PARENT_OF edge to child AND gender='male'.
    If gender is not set on that node, fall back to any PARENT_OF parent
    that is NOT the mother (i.e. the non-female parent).
    Strategy: try gender-based first, then fall back to non-female parent.
    """
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN x.name AS X""", {"n": y.lower()})
        if not rows:
            # Fallback: parent who is not female
            rows = _run("""
                MATCH (x:Person)-[:PARENT_OF]->(y:Person)
                WHERE toLower(y.name)=$n
                  AND (x.gender IS NULL OR x.gender <> 'female')
                RETURN x.name AS X LIMIT 1""", {"n": y.lower()})
        return rows
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(x.name)=$n AND x.gender='male'
            RETURN y.name AS X""", {"n": x.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
          AND x.gender='male'
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_mother(args):
    """
    FIX: Mother = person who has PARENT_OF edge to child AND gender='female'.
    Falls back to non-male parent if gender is not set.
    """
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN x.name AS X""", {"n": y.lower()})
        if not rows:
            rows = _run("""
                MATCH (x:Person)-[:PARENT_OF]->(y:Person)
                WHERE toLower(y.name)=$n
                  AND (x.gender IS NULL OR x.gender <> 'male')
                RETURN x.name AS X LIMIT 1""", {"n": y.lower()})
        return rows
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(x.name)=$n AND x.gender='female'
            RETURN y.name AS X""", {"n": x.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
          AND x.gender='female'
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_child(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n RETURN x.name AS X""", {"n": y.lower()})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(x.name)=$n RETURN y.name AS X""", {"n": x.lower()})
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_son(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (y:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN x.name AS X""", {"n": y.lower()})
        if not rows:
            rows = _run("""
                MATCH (y:Person)-[:PARENT_OF]->(x:Person)
                WHERE toLower(y.name)=$n
                  AND (x.gender IS NULL OR x.gender <> 'female')
                RETURN x.name AS X""", {"n": y.lower()})
        return rows
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn AND x.gender='male'
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_daughter(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        rows = _run("""
            MATCH (y:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN x.name AS X""", {"n": y.lower()})
        if not rows:
            rows = _run("""
                MATCH (y:Person)-[:PARENT_OF]->(x:Person)
                WHERE toLower(y.name)=$n
                  AND (x.gender IS NULL OR x.gender <> 'male')
                RETURN x.name AS X""", {"n": y.lower()})
        return rows
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn AND x.gender='female'
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


# ── Spouse ────────────────────────────────────────────────────────────────────

def _q_spouse(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(x.name)=$n RETURN y.name AS X""", {"n": x.lower()})
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(y.name)=$n RETURN x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
        RETURN x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_husband(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
        WHERE toLower(x.name)=$xn AND x.gender='male'
        RETURN x.name AS X""", {"xn": x.lower()})


def _q_wife(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:MARRIED_TO]-(y:Person)
        WHERE toLower(x.name)=$xn AND x.gender='female'
        RETURN x.name AS X""", {"xn": x.lower()})


# ── Siblings ──────────────────────────────────────────────────────────────────

def _q_sibling(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person),
                  (p:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x <> y
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person),
              (p:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn AND x <> y
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_brother(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person),
                  (p:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x <> y AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person),
              (p:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
          AND x <> y AND x.gender='male'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_sister(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(x:Person),
                  (p:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x <> y AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (p:Person)-[:PARENT_OF]->(x:Person),
              (p:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
          AND x <> y AND x.gender='female'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


# ── Grandparents ──────────────────────────────────────────────────────────────

def _q_grandparent(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_grandfather(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn AND x.gender='male'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_grandmother(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn AND x.gender='female'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_grandchild(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_grandson(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn AND x.gender='male'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_granddaughter(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (y:Person)-[:PARENT_OF]->(:Person)-[:PARENT_OF]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn AND x.gender='female'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


# ── Dada / Dadi / Nana / Nani ─────────────────────────────────────────────────

def _q_dada(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male' AND f.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
          AND x.gender='male' AND f.gender='male'
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_dadi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female' AND f.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_nana(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male' AND m.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_nani(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female' AND m.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


# ── Extended Family ───────────────────────────────────────────────────────────

def _q_uncle(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> p AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_aunt(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(p:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> p AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_cousin(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (ggp:Person)-[:PARENT_OF]->(pa:Person)-[:PARENT_OF]->(y:Person),
                  (ggp:Person)-[:PARENT_OF]->(ua:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND pa <> ua AND x <> y
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_nephew(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person),
                  (gp:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND z <> y AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_niece(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(z:Person)-[:PARENT_OF]->(x:Person),
                  (gp:Person)-[:PARENT_OF]->(y:Person)
            WHERE toLower(y.name)=$n AND z <> y AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


# ── Urdu Relations ────────────────────────────────────────────────────────────

def _q_chacha(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> f AND x.gender='male' AND f.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_phoophi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> f AND x.gender='female' AND f.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_maamu(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> m AND x.gender='male' AND m.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_khala(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> m AND x.gender='female' AND m.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_chachi(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(ch:Person),
                  (x:Person)-[:MARRIED_TO]-(ch)
            WHERE toLower(y.name)=$n AND ch <> f AND ch.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_phuppa(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(f:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(ph:Person),
                  (x:Person)-[:MARRIED_TO]-(ph)
            WHERE toLower(y.name)=$n AND ph <> f AND ph.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_maami(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(ma:Person),
                  (x:Person)-[:MARRIED_TO]-(ma)
            WHERE toLower(y.name)=$n AND ma <> m AND ma.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_khalu(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(m:Person)-[:PARENT_OF]->(y:Person),
                  (gp:Person)-[:PARENT_OF]->(kh:Person),
                  (x:Person)-[:MARRIED_TO]-(kh)
            WHERE toLower(y.name)=$n AND kh <> m AND kh.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


# ── In-Laws ───────────────────────────────────────────────────────────────────

def _q_father_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_mother_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_brother_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> s AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_sister_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (gp:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(y:Person),
                  (gp:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> s AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_son_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(d:Person)-[:MARRIED_TO]-(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='male'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


def _q_daughter_in_law(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]->(s:Person)-[:MARRIED_TO]-(x:Person)
            WHERE toLower(y.name)=$n AND x.gender='female'
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


# ── Ancestor / Descendant ─────────────────────────────────────────────────────

def _q_ancestor(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]->(y:Person)
            WHERE toLower(y.name)=$n
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]->(y:Person)
            WHERE toLower(x.name)=$n
            RETURN DISTINCT y.name AS X""", {"n": x.lower()})
    return _run("""
        MATCH (x:Person)-[:PARENT_OF*1..]->(y:Person)
        WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_descendant(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF*1..]->(x:Person)
            WHERE toLower(y.name)=$n
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return _run("""
        MATCH (y:Person)-[:PARENT_OF*1..]->(x:Person)
        WHERE toLower(y.name)=$yn AND toLower(x.name)=$xn
        RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})


def _q_blood_relative(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]-(y:Person)
            WHERE toLower(y.name)=$n AND x <> y
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    if not _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]-(y:Person)
            WHERE toLower(x.name)=$xn AND toLower(y.name)=$yn
            RETURN DISTINCT x.name AS X""", {"xn": x.lower(), "yn": y.lower()})
    return []


def _q_family_member(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (y:Person)-[:PARENT_OF]-(x:Person)
            WHERE toLower(y.name)=$n
            RETURN DISTINCT x.name AS X
            UNION
            MATCH (p:Person)-[:PARENT_OF]->(y:Person),
                  (p:Person)-[:PARENT_OF]->(x:Person)
            WHERE toLower(y.name)=$n AND x <> y
            RETURN DISTINCT x.name AS X""", {"n": y.lower()})
    return []


# ── Properties ────────────────────────────────────────────────────────────────

def _q_dob(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.dob IS NOT NULL RETURN p.dob AS X",
            {"n": x.lower()})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {dob:$d}) RETURN p.name AS X", {"d": y})
    return []


def _q_occupation(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.occupation IS NOT NULL RETURN p.occupation AS X",
            {"n": x.lower()})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person) WHERE p.occupation=$occ RETURN p.name AS X", {"occ": y})
    if _is_var(x) and _is_var(y):
        return _run("MATCH (p:Person) WHERE p.occupation IS NOT NULL RETURN p.name AS X, p.occupation AS Y")
    return []


def _q_lives_in(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.city IS NOT NULL RETURN p.city AS X",
            {"n": x.lower()})
    if _is_var(x) and not _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE toLower(p.city)=toLower($city) RETURN p.name AS X",
            {"city": y})
    if _is_var(x) and _is_var(y):
        return _run("MATCH (p:Person) WHERE p.city IS NOT NULL RETURN p.name AS X, p.city AS Y")
    return _run(
        "MATCH (p:Person) WHERE toLower(p.name)=$xn AND toLower(p.city)=toLower($yn) RETURN p.name AS X",
        {"xn": x.lower(), "yn": y.lower()})


def _q_religion(args):
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE toLower(p.name)=$n AND p.religion IS NOT NULL RETURN p.religion AS X",
            {"n": x.lower()})
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person) WHERE p.religion=$r RETURN p.name AS X", {"r": y})
    if _is_var(x) and _is_var(y):
        return _run("MATCH (p:Person) WHERE p.religion IS NOT NULL RETURN p.name AS X, p.religion AS Y")
    return []


# ── Same group ────────────────────────────────────────────────────────────────

def _q_same_city(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (a:Person), (b:Person)
            WHERE toLower(a.name)=$n AND a.city IS NOT NULL
              AND toLower(a.city)=toLower(b.city) AND a <> b
            RETURN DISTINCT b.name AS X""", {"n": name.lower()})
    return []


def _q_same_occupation(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (a:Person), (b:Person)
            WHERE toLower(a.name)=$n AND a.occupation IS NOT NULL
              AND a.occupation=b.occupation AND a <> b
            RETURN DISTINCT b.name AS X""", {"n": name.lower()})
    return []


def _q_same_generation(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    if name:
        return _run("""
            MATCH (p:Person)-[:PARENT_OF]->(a:Person),
                  (p:Person)-[:PARENT_OF]->(b:Person)
            WHERE toLower(a.name)=$n AND a <> b
            RETURN DISTINCT b.name AS X
            UNION
            MATCH (gp:Person)-[:PARENT_OF]->()-[:PARENT_OF]->(a:Person),
                  (gp:Person)-[:PARENT_OF]->()-[:PARENT_OF]->(b:Person)
            WHERE toLower(a.name)=$n AND a <> b
            RETURN DISTINCT b.name AS X""", {"n": name.lower()})
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