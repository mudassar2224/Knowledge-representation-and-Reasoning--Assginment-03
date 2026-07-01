# graph_inference.py
# Priority 2: Inference and Knowledge Discovery
# Satisfies assignment requirement 5: Discover mutual connections,
# hidden relationships, and recommendations.

from neo4j_engine import _run


def find_mutual_connections(name1: str, name2: str) -> list:
    """
    Find people connected to BOTH name1 and name2.
    Example: who do Ali and Asad have in common (shared parent, shared relative, etc.)
    """
    n1, n2 = name1.lower().strip(), name2.lower().strip()
    rows = _run("""
        MATCH (a:Person {name:$n1})-[]-(common:Person)-[]-(b:Person {name:$n2})
        WHERE common <> a AND common <> b
        RETURN DISTINCT common.name AS name
    """, {"n1": n1, "n2": n2})
    return [r["name"] for r in rows if r.get("name")]


def find_mutual_relatives(name1: str, name2: str) -> list:
    """
    Find blood relatives common to both people via PARENT_OF traversal.
    A stricter version of mutual_connections limited to family lineage.
    """
    n1, n2 = name1.lower().strip(), name2.lower().strip()
    rows = _run("""
        MATCH (a:Person {name:$n1})-[:PARENT_OF*1..3]-(common:Person),
              (b:Person {name:$n2})-[:PARENT_OF*1..3]-(common:Person)
        WHERE common <> a AND common <> b
        RETURN DISTINCT common.name AS name
    """, {"n1": n1, "n2": n2})
    return [r["name"] for r in rows if r.get("name")]


def discover_hidden_relationships(name: str) -> list:
    """
    Discover relationships not directly stored but inferable through
    multi-hop graph traversal — e.g. 2nd cousins, in-laws of in-laws,
    or any person reachable within 3 hops that has no direct PARENT_OF
    or MARRIED_TO edge to this person.
    """
    n = name.lower().strip()
    rows = _run("""
        MATCH (a:Person {name:$n})-[*2..3]-(hidden:Person)
        WHERE hidden <> a
          AND NOT (a)-[:PARENT_OF]-(hidden)
          AND NOT (a)-[:MARRIED_TO]-(hidden)
        RETURN DISTINCT hidden.name AS name
    """, {"n": n})
    return [r["name"] for r in rows if r.get("name")]


def recommend_connections(name: str) -> list:
    """
    Recommend people the given person is NOT yet connected to,
    but who share city or occupation (potential meaningful connections).
    This is the 'recommendation' feature required by the assignment.
    """
    n = name.lower().strip()
    rows = _run("""
        MATCH (a:Person {name:$n})
        MATCH (candidate:Person)
        WHERE candidate <> a
          AND NOT (a)-[]-(candidate)
          AND (
                (a.city IS NOT NULL AND candidate.city = a.city)
             OR (a.occupation IS NOT NULL AND candidate.occupation = a.occupation)
          )
        RETURN DISTINCT candidate.name AS name,
               candidate.city AS city,
               candidate.occupation AS occupation
    """, {"n": n})
    return rows


def shortest_path_between(name1: str, name2: str) -> dict:
    """
    Find the shortest relationship path between two people,
    demonstrating graph traversal depth as required by the assignment.
    Returns path length and the sequence of names along the path.
    """
    n1, n2 = name1.lower().strip(), name2.lower().strip()
    rows = _run("""
        MATCH path = shortestPath(
            (a:Person {name:$n1})-[*]-(b:Person {name:$n2})
        )
        RETURN [node IN nodes(path) | node.name] AS names,
               length(path) AS hops
    """, {"n1": n1, "n2": n2})
    if rows:
        return {"names": rows[0]["names"], "hops": rows[0]["hops"]}
    return {}


def get_connection_strength(name1: str, name2: str) -> dict:
    """
    Inference: classify how closely two people are connected
    based on path length (hop count) — demonstrates reasoning
    over the graph structure rather than simple direct lookup.
    """
    path = shortest_path_between(name1, name2)
    if not path:
        return {"connected": False}

    hops = path["hops"]
    if hops == 0:
        strength = "same person"
    elif hops == 1:
        strength = "immediate family (direct relationship)"
    elif hops == 2:
        strength = "close family (e.g. sibling, grandparent, in-law)"
    elif hops == 3:
        strength = "extended family (e.g. cousin, uncle/aunt)"
    else:
        strength = "distant connection"

    return {
        "connected": True,
        "hops": hops,
        "strength": strength,
        "path": path["names"],
    }


# ── Natural language formatters ───────────────────────────────────────────────

def format_mutual_connections_response(name1: str, name2: str) -> str:
    from utils import capitalize_name
    common = find_mutual_relatives(name1, name2)
    n1c, n2c = capitalize_name(name1), capitalize_name(name2)

    if not common:
        common = find_mutual_connections(name1, name2)

    if not common:
        return f"{n1c} and {n2c} do not appear to have any connections in common."

    names = ", ".join(capitalize_name(n) for n in common)
    return f"{n1c} and {n2c} have the following in common: {names}."


def format_hidden_relationships_response(name: str) -> str:
    from utils import capitalize_name
    hidden = discover_hidden_relationships(name)
    name_cap = capitalize_name(name)

    if not hidden:
        return f"No hidden or indirect relationships discovered for {name_cap} beyond what is already known."

    names = ", ".join(capitalize_name(n) for n in hidden)
    return (
        f"Discovered hidden relationships for {name_cap} through graph traversal "
        f"(people connected within 2-3 hops, not directly stated): {names}."
    )


def format_recommendations_response(name: str) -> str:
    from utils import capitalize_name, format_value
    candidates = recommend_connections(name)
    name_cap = capitalize_name(name)

    if not candidates:
        return f"No new connection recommendations found for {name_cap} at this time."

    lines = [f"Recommended connections for {name_cap} (based on shared city or occupation):"]
    for c in candidates[:5]:
        reason_parts = []
        if c.get("city"):
            reason_parts.append(f"same city ({format_value(c['city'])})")
        if c.get("occupation"):
            reason_parts.append(f"same occupation ({format_value(c['occupation'])})")
        reason = " and ".join(reason_parts) if reason_parts else "shared attribute"
        lines.append(f"- {capitalize_name(c['name'])} ({reason})")
    return "\n".join(lines)


def format_connection_strength_response(name1: str, name2: str) -> str:
    from utils import capitalize_name
    n1c, n2c = capitalize_name(name1), capitalize_name(name2)
    result = get_connection_strength(name1, name2)

    if not result.get("connected"):
        return f"{n1c} and {n2c} are not connected in the graph at all."

    path_names = " → ".join(capitalize_name(n) for n in result["path"])
    return (
        f"{n1c} and {n2c} are connected through {result['hops']} hop(s): "
        f"{path_names}.\n"
        f"Inferred relationship strength: {result['strength']}."
    )