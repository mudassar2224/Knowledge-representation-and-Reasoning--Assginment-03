# graph_builder.py
# Assignment 3: Replaces fact_builder.py
# Creates Person nodes and PARENT_OF / MARRIED_TO edges in Neo4j.
# No Prolog file writing — data goes directly into the graph.

import re
from neo4j_engine import _run, person_exists_in_graph


def person_exists(name: str) -> bool:
    """Check if a Person node already exists."""
    return person_exists_in_graph(name.lower().strip())


def save_to_graph(data: dict) -> tuple:
    """
    Create a Person node and its relationships in Neo4j.

    Assignment steps fulfilled here:
      Step 5 (string handling): data dict → Cypher parameters
      Step 6 (file/DB handling): MERGE statements write to Neo4j graph

    Args:
        data: dict with keys name, gender, father, mother,
              dob, city, occupation, religion, spouse

    Returns:
        (True, success_message) or (False, error_message)
    """
    name       = data.get("name",       "").lower().strip()
    gender     = data.get("gender",     "").lower().strip()
    father     = data.get("father",     "unknown").lower().strip()
    mother     = data.get("mother",     "unknown").lower().strip()
    dob        = data.get("dob",        "unknown").strip()
    city       = data.get("city",       "unknown").lower().strip()
    occupation = data.get("occupation", "unknown").lower().strip()
    religion   = data.get("religion",   "unknown").lower().strip()
    spouse     = data.get("spouse",     "unknown").lower().strip()

    # Validate name is a safe atom
    if not name or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return False, f"Invalid name '{name}'. Use letters only (e.g. ali or ali_hassan)."

    try:
        # ── Step 1: Create / update the Person node ───────────────────────────
        _run("""
            MERGE (p:Person {name: $name})
            SET p.gender = $gender
        """, {"name": name, "gender": gender})

        # Set optional properties only when not "unknown"
        if dob and dob.lower() != "unknown":
            _run("MATCH (p:Person {name:$n}) SET p.dob = $v",
                 {"n": name, "v": dob})

        if city and city != "unknown":
            _run("MATCH (p:Person {name:$n}) SET p.city = $v",
                 {"n": name, "v": city})

        if occupation and occupation != "unknown":
            _run("MATCH (p:Person {name:$n}) SET p.occupation = $v",
                 {"n": name, "v": occupation})

        if religion and religion != "unknown":
            _run("MATCH (p:Person {name:$n}) SET p.religion = $v",
                 {"n": name, "v": religion})

        # ── Step 2: PARENT_OF from father ────────────────────────────────────
        if father and father != "unknown":
            _run("""
                MERGE (f:Person {name: $father})
                WITH f
                MATCH (c:Person {name: $child})
                MERGE (f)-[:PARENT_OF]->(c)
            """, {"father": father, "child": name})

        # ── Step 3: PARENT_OF from mother ────────────────────────────────────
        if mother and mother != "unknown":
            _run("""
                MERGE (m:Person {name: $mother})
                WITH m
                MATCH (c:Person {name: $child})
                MERGE (m)-[:PARENT_OF]->(c)
            """, {"mother": mother, "child": name})

        # ── Step 4: MARRIED_TO relationship ──────────────────────────────────
        if spouse and spouse != "unknown":
            _run("""
                MERGE (a:Person {name: $name})
                MERGE (b:Person {name: $spouse})
                MERGE (a)-[:MARRIED_TO]->(b)
            """, {"name": name, "spouse": spouse})

        print(f"[Neo4j] Created node + relationships for '{name}'.")
        return True, f"Added {name} to Neo4j graph."

    except Exception as e:
        print(f"[Neo4j ERROR] save_to_graph('{name}'): {e}")
        return False, str(e)