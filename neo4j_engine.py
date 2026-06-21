# neo4j_engine.py
# Assignment 3: Replaces prolog_engine.py
# All Prolog rules are now written as Cypher graph queries.
#
# SCHEMA:
#   Node  : (:Person {name, gender, dob, occupation, city, religion})
#   Edges : [:PARENT_OF]   (parent)-[:PARENT_OF]->(child)
#           [:MARRIED_TO]  (person)-[:MARRIED_TO]->(spouse)

from neo4j import GraphDatabase
from neo4j_config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

_driver = None


# ── Connection helpers ────────────────────────────────────────────────────────

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    return _driver


def _run(cypher: str, params: dict = None) -> list:
    """Execute Cypher and return a list of record dicts."""
    try:
        with _get_driver().session() as session:
            result = session.run(cypher, params or {})
            return [dict(r) for r in result]
    except Exception as e:
        print(f"[Neo4j ERROR] {e}")
        return []


def _is_var(s: str) -> bool:
    """True if s is a Prolog-style variable (starts with uppercase)."""
    s = str(s).strip()
    return bool(s) and s[0].isupper()


# ── Public API ────────────────────────────────────────────────────────────────

def load_graph():
    """Test the Neo4j connection and report graph size."""
    try:
        rows = _run("MATCH (p:Person) RETURN count(p) AS n")
        n = rows[0]["n"] if rows else 0
        print(f"[Neo4j] Connected to local Neo4j. {n} people in graph.")
        return True
    except Exception as e:
        print(f"[Neo4j ERROR] Connection failed: {e}")
        print("  Make sure Neo4j Desktop is running on bolt://localhost:7687")
        return False


def reload_graph():
    """Sync KNOWN_NAMES from the graph after a person is added."""
    import utils
    people = get_all_people()
    utils.KNOWN_NAMES.update(people)
    print(f"[Neo4j] Synced. {len(people)} people: {sorted(people)}")


def get_all_people() -> set:
    """Return all person names currently in the graph."""
    rows = _run("MATCH (p:Person) RETURN p.name AS name")
    return {r["name"] for r in rows if r.get("name")}


def person_exists_in_graph(name: str) -> bool:
    rows = _run(
        "MATCH (p:Person {name:$name}) RETURN p.name",
        {"name": name.lower()}
    )
    return len(rows) > 0


# ── Individual Cypher query functions ────────────────────────────────────────
# Each function mirrors one Prolog rule.
# Convention: _is_var(x) means x is the variable to find.
# All results return {"X": value} to match the prolog_engine interface.

# ── Gender ───────────────────────────────────────────────────────────────────

def _q_male(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'male'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person {name:$n}) WHERE p.gender='male' RETURN p.name AS X",
        {"n": x}
    )


def _q_female(args):
    x = args[0]
    if _is_var(x):
        return _run("MATCH (p:Person {gender:'female'}) RETURN p.name AS X")
    return _run(
        "MATCH (p:Person {name:$n}) WHERE p.gender='female' RETURN p.name AS X",
        {"n": x}
    )


# ── Parent / Child ────────────────────────────────────────────────────────────

def _q_parent(args):
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run(
            "MATCH (x:Person)-[:PARENT_OF]->(y:Person {name:$n}) RETURN x.name AS X",
            {"n": y}
        )
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (x:Person {name:$n})-[:PARENT_OF]->(y:Person) RETURN y.name AS X",
            {"n": x}
        )
    return _run(
        "MATCH (x:Person {name:$xn})-[:PARENT_OF]->(y:Person {name:$yn}) RETURN x.name AS X",
        {"xn": x, "yn": y}
    )


def _q_father(args):
    """father(X, Y) :- male(X), parent(X, Y)."""
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'male'})-[:PARENT_OF]->(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n, gender:'male'})-[:PARENT_OF]->(y:Person)
            RETURN y.name AS X""", {"n": x})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'male'})-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_mother(args):
    """mother(X, Y) :- female(X), parent(X, Y)."""
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person {gender:'female'})-[:PARENT_OF]->(y:Person {name:$n})
            RETURN x.name AS X""", {"n": y})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n, gender:'female'})-[:PARENT_OF]->(y:Person)
            RETURN y.name AS X""", {"n": x})
    return _run("""
        MATCH (x:Person {name:$xn, gender:'female'})-[:PARENT_OF]->(y:Person {name:$yn})
        RETURN x.name AS X""", {"xn": x, "yn": y})


def _q_child(args):
    """child(X, Y) :- parent(Y, X)."""
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
    """spouse(X, Y) :- married(X, Y) or married(Y, X). Uses undirected match."""
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
    """sibling(X, Y) :- parent(Z, X), parent(Z, Y), X ≠ Y."""
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
    """Paternal grandfather: father's father."""
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
    """Paternal grandmother: father's mother."""
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
    """Maternal grandfather: mother's father."""
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
    """Maternal grandmother: mother's mother."""
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
    """Uncle: male sibling of a parent of Y."""
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
    """Aunt: female sibling of a parent of Y."""
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
    """Cousin: child of sibling of parent of Y."""
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
    """Nephew: male child of a sibling of Y."""
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
    """Niece: female child of a sibling of Y."""
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
    """Chacha: father's brother."""
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
    """Phoophi: father's sister."""
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
    """Maamu: mother's brother."""
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
    """Khala: mother's sister."""
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
    """Chachi: wife of chacha."""
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
    """Phuppa: husband of phoophi."""
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
    """Maami: wife of maamu."""
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
    """Khalu: husband of khala."""
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


# ── Ancestor / Descendant (recursive) ────────────────────────────────────────
# Cypher's [:PARENT_OF*1..] traverses any number of hops automatically.
# This replaces the recursive Prolog ancestor rule.

def _q_ancestor(args):
    """ancestor(X, Y) :- parent(X,Y). ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y)."""
    x, y = args[0], args[1]
    if _is_var(x) and not _is_var(y):
        return _run("""
            MATCH (x:Person)-[:PARENT_OF*1..]->(y:Person {name:$n})
            RETURN DISTINCT x.name AS X""", {"n": y})
    if not _is_var(x) and _is_var(y):
        return _run("""
            MATCH (x:Person {name:$n})-[:PARENT_OF*1..]->(y:Person)
            RETURN DISTINCT y.name AS X""", {"n": x})
    return _run("""
        MATCH (x:Person {name:$xn})-[:PARENT_OF*1..]->(y:Person {name:$yn})
        RETURN DISTINCT x.name AS X""", {"xn": x, "yn": y})


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
    """
    Any two people connected through PARENT_OF edges (directed or undirected).
    The undirected - in Cypher covers ancestors, descendants, and cousins.
    """
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
    """dob(Person, DateValue)"""
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.dob IS NOT NULL RETURN p.dob AS X",
            {"n": x}
        )
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {dob:$d}) RETURN p.name AS X", {"d": y})
    return []


def _q_occupation(args):
    """occupation(Person, Job)"""
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.occupation IS NOT NULL RETURN p.occupation AS X",
            {"n": x}
        )
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {occupation:$occ}) RETURN p.name AS X", {"occ": y})
    if _is_var(x) and _is_var(y):
        # Used by streamlit_app._family_occupations() with var="Y"
        return _run(
            "MATCH (p:Person) WHERE p.occupation IS NOT NULL RETURN p.name AS X, p.occupation AS Y"
        )
    return []


def _q_lives_in(args):
    """lives_in(Person, City)"""
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.city IS NOT NULL RETURN p.city AS X",
            {"n": x}
        )
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {city:$city}) RETURN p.name AS X", {"city": y})
    if _is_var(x) and _is_var(y):
        # Used by streamlit_app._family_cities() with var="Y"
        return _run(
            "MATCH (p:Person) WHERE p.city IS NOT NULL RETURN p.name AS X, p.city AS Y"
        )
    return _run(
        "MATCH (p:Person {name:$xn, city:$yn}) RETURN p.name AS X",
        {"xn": x, "yn": y}
    )


def _q_religion(args):
    """religion(Person, Religion)"""
    x, y = args[0], args[1]
    if not _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person {name:$n}) WHERE p.religion IS NOT NULL RETURN p.religion AS X",
            {"n": x}
        )
    if _is_var(x) and not _is_var(y):
        return _run("MATCH (p:Person {religion:$r}) RETURN p.name AS X", {"r": y})
    if _is_var(x) and _is_var(y):
        return _run(
            "MATCH (p:Person) WHERE p.religion IS NOT NULL RETURN p.name AS X, p.religion AS Y"
        )
    return []


# ── Same group ────────────────────────────────────────────────────────────────

def _q_same_city(args):
    x, y = args[0], args[1]
    name = x if not _is_var(x) else y if not _is_var(y) else None
    other_var = _is_var(y) if not _is_var(x) else _is_var(x)
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
    "married":         _q_spouse,       # alias
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
    """
    Execute a family relationship query against Neo4j.
    Mirrors the prolog_engine.query() interface exactly.
    Returns [{"X": value}, ...] or [{"X": v1, "Y": v2}, ...] for both-variable queries.
    """
    fn = _QUERY_MAP.get(relation)
    if fn is None:
        return []
    try:
        return fn(args) or []
    except Exception as e:
        print(f"[Neo4j ERROR] query({relation}, {args}): {e}")
        return []


def query_yes_no(relation: str, args: list) -> bool:
    """Check if a ground relation holds. Returns True/False."""
    return bool(query(relation, args))