# graph_analysis.py
# Priority 1: Graph-Based Analysis
# Satisfies assignment requirement 3: Analyze node labels,
# relationship types, properties, and graph structures.

from neo4j_engine import _run


def get_node_labels() -> list:
    """Return all distinct node labels in the graph."""
    rows = _run("CALL db.labels() YIELD label RETURN label")
    return sorted([r["label"] for r in rows])


def get_relationship_types() -> list:
    """Return all distinct relationship types in the graph."""
    rows = _run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
    return sorted([r["relationshipType"] for r in rows])


def get_property_keys() -> list:
    """Return all distinct property keys used anywhere in the graph."""
    rows = _run("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey")
    return sorted([r["propertyKey"] for r in rows])


def get_graph_stats() -> dict:
    """Return overall graph statistics: node count, relationship count, etc."""
    node_count = _run("MATCH (n) RETURN count(n) AS c")
    rel_count  = _run("MATCH ()-[r]->() RETURN count(r) AS c")
    person_count = _run("MATCH (p:Person) RETURN count(p) AS c")

    return {
        "total_nodes": node_count[0]["c"] if node_count else 0,
        "total_relationships": rel_count[0]["c"] if rel_count else 0,
        "total_people": person_count[0]["c"] if person_count else 0,
        "labels": get_node_labels(),
        "relationship_types": get_relationship_types(),
        "property_keys": get_property_keys(),
    }


def get_most_connected_person() -> dict:
    """
    Find the person with the most relationships (highest degree).
    Demonstrates graph-based structural analysis.
    """
    rows = _run("""
        MATCH (p:Person)-[r]-()
        RETURN p.name AS name, count(r) AS degree
        ORDER BY degree DESC
        LIMIT 1
    """)
    if rows:
        return {"name": rows[0]["name"], "connections": rows[0]["degree"]}
    return {}


def get_relationship_type_counts() -> dict:
    """Count how many relationships exist of each type."""
    rows = _run("""
        MATCH ()-[r]->()
        RETURN type(r) AS rel_type, count(r) AS count
        ORDER BY count DESC
    """)
    return {r["rel_type"]: r["count"] for r in rows}


def get_isolated_people() -> list:
    """Find people with no relationships at all (orphan nodes)."""
    rows = _run("""
        MATCH (p:Person)
        WHERE NOT (p)-[]-()
        RETURN p.name AS name
    """)
    return [r["name"] for r in rows]


def get_person_degree(name: str) -> int:
    """Return how many relationships a specific person has (their connectivity)."""
    rows = _run("""
        MATCH (p:Person {name:$n})-[r]-()
        RETURN count(r) AS degree
    """, {"n": name.lower().strip()})
    return rows[0]["degree"] if rows else 0


def get_property_completeness() -> dict:
    """
    Show what percentage of Person nodes have each optional property set.
    Useful for demonstrating data quality analysis on the graph.
    """
    total = _run("MATCH (p:Person) RETURN count(p) AS c")
    total_count = total[0]["c"] if total else 0
    if total_count == 0:
        return {}

    result = {}
    for prop in ("dob", "city", "occupation", "religion"):
        rows = _run(f"""
            MATCH (p:Person)
            WHERE p.{prop} IS NOT NULL
            RETURN count(p) AS c
        """)
        filled = rows[0]["c"] if rows else 0
        result[prop] = {
            "filled": filled,
            "total": total_count,
            "percent": round((filled / total_count) * 100, 1) if total_count else 0,
        }
    return result


def format_graph_stats_response() -> str:
    """Build a natural-language summary of the graph structure."""
    stats = get_graph_stats()

    if stats["total_people"] == 0:
        return "The graph is currently empty. Type 'add person' to add the first family member."

    lines = ["Here is the current graph structure:"]
    lines.append(f"- Total nodes: {stats['total_nodes']}")
    lines.append(f"- Total relationships: {stats['total_relationships']}")
    lines.append(f"- Total people: {stats['total_people']}")
    lines.append(f"- Node labels: {', '.join(stats['labels']) if stats['labels'] else 'none'}")
    lines.append(f"- Relationship types: {', '.join(stats['relationship_types']) if stats['relationship_types'] else 'none'}")
    lines.append(f"- Properties tracked: {', '.join(stats['property_keys']) if stats['property_keys'] else 'none'}")
    return "\n".join(lines)


def format_relationship_breakdown_response() -> str:
    """Build a natural-language breakdown of relationship type counts."""
    counts = get_relationship_type_counts()
    if not counts:
        return "No relationships found in the graph yet."

    lines = ["Relationship type breakdown:"]
    for rel_type, count in counts.items():
        lines.append(f"- {rel_type}: {count}")
    return "\n".join(lines)


def format_most_connected_response() -> str:
    """Build a natural-language answer about the most connected person."""
    top = get_most_connected_person()
    if not top:
        return "No connections found in the graph yet."
    name = top["name"].replace("_", " ").title()
    return f"{name} is the most connected person in the graph with {top['connections']} relationships."


def format_completeness_response() -> str:
    """Build a natural-language data quality report."""
    completeness = get_property_completeness()
    if not completeness:
        return "The graph is empty, so there is no data quality information yet."

    lines = ["Data completeness across all people:"]
    for prop, info in completeness.items():
        lines.append(
            f"- {prop}: {info['filled']}/{info['total']} people ({info['percent']}%)"
        )
    return "\n".join(lines)