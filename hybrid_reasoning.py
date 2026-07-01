# hybrid_reasoning.py
# Priority 3 (Bonus): Hybrid Neo4j-Prolog Reasoning
# Converts Neo4j graph data → Prolog facts → runs Pytholog inference
# → writes newly inferred relationships back into Neo4j.
#
# Demonstrates the assignment's learning outcome:
# "Compare rule-based reasoning (Prolog) with graph-based reasoning (Neo4j)."

import re
import pytholog as pl

from neo4j_engine import _run


# ── Step 1: Extract Neo4j graph data as Prolog facts ─────────────────────────

def export_graph_to_prolog_facts() -> list:
    """
    Read all Person nodes and relationships from Neo4j and convert
    them into Prolog fact strings (string handling, mirrors A2 logic).
    """
    facts = []

    # Gender facts
    rows = _run("MATCH (p:Person) WHERE p.gender IS NOT NULL RETURN p.name AS name, p.gender AS gender")
    for r in rows:
        facts.append(f"{r['gender']}({r['name']})")

    # Parent facts (from PARENT_OF edges)
    rows = _run("MATCH (a:Person)-[:PARENT_OF]->(b:Person) RETURN a.name AS parent, b.name AS child")
    for r in rows:
        facts.append(f"parent({r['parent']}, {r['child']})")

    # Married facts (from MARRIED_TO edges)
    rows = _run("MATCH (a:Person)-[:MARRIED_TO]->(b:Person) RETURN a.name AS x, b.name AS y")
    for r in rows:
        facts.append(f"married({r['x']}, {r['y']})")

    # different/2 facts (needed by sibling/cousin rules, same as A1/A2)
    names = _run("MATCH (p:Person) RETURN p.name AS name")
    name_list = sorted({r["name"] for r in names if r.get("name")})
    for i, n1 in enumerate(name_list):
        for n2 in name_list[i + 1:]:
            facts.append(f"different({n1}, {n2})")
            facts.append(f"different({n2}, {n1})")

    return facts


# ── Step 2: Define the Prolog inference rules ─────────────────────────────────

PROLOG_RULES = """
father(X, Y) :- male(X), parent(X, Y).
mother(X, Y) :- female(X), parent(X, Y).
sibling(X, Y) :- parent(Z, X), parent(Z, Y), different(X, Y).
brother(X, Y) :- sibling(X, Y), male(X).
sister(X, Y) :- sibling(X, Y), female(X).
grandparent(X, Y) :- parent(X, Z), parent(Z, Y).
grandfather(X, Y) :- father(X, Z), parent(Z, Y).
grandmother(X, Y) :- mother(X, Z), parent(Z, Y).
uncle(X, Y) :- brother(X, Z), parent(Z, Y).
aunt(X, Y) :- sister(X, Z), parent(Z, Y).
cousin(X, Y) :- parent(A, X), parent(B, Y), sibling(A, B), different(X, Y).
ancestor(X, Y) :- parent(X, Y).
ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).
"""


# ── Step 3: Build a temporary Pytholog KB from Neo4j data ────────────────────

def build_prolog_kb():
    """
    Load exported facts + fixed rules into a fresh in-memory Pytholog KB.
    This is the 'rule-based reasoning' side of the hybrid comparison.
    """
    kb = pl.KnowledgeBase("hybrid")

    clauses = export_graph_to_prolog_facts()

    for line in PROLOG_RULES.strip().split("\n"):
        line = line.strip()
        if line:
            clauses.append(line.rstrip("."))

    kb(clauses)
    return kb


# ── Step 4: Run inference and discover NEW relationships ─────────────────────

def infer_new_relationships() -> dict:
    """
    Run Prolog inference over the exported graph data to discover
    relationships that exist logically but have not yet been
    explicitly written back into Neo4j as relationships
    (e.g. uncle, grandparent, cousin — all derived, not stored directly).

    Returns a dict: {relation_name: [(x, y), ...]}
    """
    kb = build_prolog_kb()
    names_rows = _run("MATCH (p:Person) RETURN p.name AS name")
    names = sorted({r["name"] for r in names_rows if r.get("name")})

    inferred = {
        "grandparent": [],
        "uncle": [],
        "aunt": [],
        "cousin": [],
        "ancestor": [],
    }

    for relation in inferred:
        for n in names:
            try:
                results = kb.query(pl.Expr(f"{relation}(X, {n})"))
            except Exception:
                results = []
            if not results:
                continue
            for item in results:
                if isinstance(item, dict):
                    x = item.get("X", "")
                    if x and x != "No":
                        inferred[relation].append((x, n))

    # Deduplicate
    for relation in inferred:
        inferred[relation] = sorted(set(inferred[relation]))

    return inferred


# ── Step 5: Write inferred knowledge back into Neo4j ──────────────────────────

def write_inferred_relationships_to_neo4j(inferred: dict) -> int:
    """
    Take Prolog-inferred relationships and write them back into Neo4j
    as labeled relationships (e.g. INFERRED_GRANDPARENT, INFERRED_UNCLE).
    This completes the hybrid loop: Neo4j → Prolog → Neo4j.

    Returns the count of relationships written.
    """
    written = 0
    rel_type_map = {
        "grandparent": "INFERRED_GRANDPARENT",
        "uncle":       "INFERRED_UNCLE",
        "aunt":        "INFERRED_AUNT",
        "cousin":      "INFERRED_COUSIN",
        "ancestor":    "INFERRED_ANCESTOR",
    }

    for relation, pairs in inferred.items():
        rel_type = rel_type_map.get(relation)
        if not rel_type:
            continue
        for x, y in pairs:
            _run(f"""
                MATCH (a:Person {{name:$x}}), (b:Person {{name:$y}})
                MERGE (a)-[:{rel_type}]->(b)
            """, {"x": x, "y": y})
            written += 1

    return written


# ── Step 6: Full hybrid reasoning pipeline ────────────────────────────────────

def run_hybrid_reasoning() -> dict:
    """
    Complete pipeline: export graph → Prolog inference → write back to Neo4j.
    Returns a summary report for display to the user.
    """
    inferred = infer_new_relationships()
    written = write_inferred_relationships_to_neo4j(inferred)

    summary = {
        "grandparent_pairs": len(inferred["grandparent"]),
        "uncle_pairs": len(inferred["uncle"]),
        "aunt_pairs": len(inferred["aunt"]),
        "cousin_pairs": len(inferred["cousin"]),
        "ancestor_pairs": len(inferred["ancestor"]),
        "total_written": written,
        "details": inferred,
    }
    return summary


# ── Natural language formatter ────────────────────────────────────────────────

def format_hybrid_reasoning_response() -> str:
    """Build a natural-language report of the hybrid reasoning run."""
    from utils import capitalize_name

    summary = run_hybrid_reasoning()

    if summary["total_written"] == 0:
        return (
            "Hybrid reasoning ran successfully, but no new inferred "
            "relationships were found. Add more family members with "
            "shared parents to generate grandparent, uncle, aunt, "
            "or cousin relationships."
        )

    lines = [
        "Hybrid Neo4j-Prolog reasoning completed.",
        "Exported graph facts → ran Prolog inference rules → wrote results back to Neo4j.",
        "",
        f"Inferred and stored {summary['total_written']} new relationships:",
        f"- Grandparent relationships: {summary['grandparent_pairs']}",
        f"- Uncle relationships: {summary['uncle_pairs']}",
        f"- Aunt relationships: {summary['aunt_pairs']}",
        f"- Cousin relationships: {summary['cousin_pairs']}",
        f"- Ancestor relationships: {summary['ancestor_pairs']}",
        "",
        "These are now stored in Neo4j as INFERRED_* relationship types,",
        "demonstrating that rule-based Prolog inference and graph-based",
        "Neo4j storage can work together in a hybrid reasoning loop.",
    ]

    # Show a few example pairs for demonstration
    for relation, pairs in summary["details"].items():
        if pairs:
            example = pairs[0]
            lines.append(
                f"\nExample — {relation}: "
                f"{capitalize_name(example[0])} is {relation} of {capitalize_name(example[1])}"
            )
            break

    return "\n".join(lines)