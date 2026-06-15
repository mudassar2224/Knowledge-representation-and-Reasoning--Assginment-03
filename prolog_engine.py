# Pytholog wrapper - A2 adds reload_kb() and get_all_people()

import os

import pytholog as pl

from utils import RELATION_NAMES, is_safe_atom, is_variable, normalize_atom


_kb = None


def load_kb():
    """Load family_kb.pl into the Pytholog knowledge base."""
    global _kb

    kb_path = os.path.join(os.path.dirname(__file__), "family_kb.pl")
    _kb = pl.KnowledgeBase("family")

    clauses = []
    current = ""
    with open(kb_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            current += " " + line
            if line.endswith("."):
                clauses.append(current.strip().rstrip("."))
                current = ""

    _kb(clauses)
    print(f"[Prolog] Knowledge base loaded ({len(clauses)} clauses).")
    return _kb


# ── A2: Reload after dynamic fact addition ──────────────────────────────────
def reload_kb():
    """
    Re-read family_kb.pl from disk after new facts have been appended.
    Also syncs utils.KNOWN_NAMES with the people now in the KB.
    """
    global _kb
    _kb = None
    load_kb()

    import utils
    people = get_all_people()
    utils.KNOWN_NAMES.update(people)
    print(f"[Prolog] KB reloaded. {len(people)} people now in KB: {sorted(people)}")
    return _kb


# ── A2: Get every person currently in the KB ────────────────────────────────
def get_all_people():
    """Return a set of all person atoms currently registered as male or female."""
    males   = set(_values(query("male",   ["X"])))
    females = set(_values(query("female", ["X"])))
    return males | females


def get_kb():
    global _kb
    if _kb is None:
        load_kb()
    return _kb


def _safe_relation(relation):
    return relation in RELATION_NAMES and is_safe_atom(relation)


def _safe_arg(arg):
    return is_variable(arg) or is_safe_atom(arg)


def _normalize_args(args):
    normalized = []
    for arg in args:
        arg = str(arg).strip()
        if is_variable(arg):
            normalized.append(arg)
            continue
        atom = normalize_atom(arg)
        if not is_safe_atom(atom):
            return None
        normalized.append(atom)
    return normalized


def query(relation, args):
    """Run a Prolog query and return raw Pytholog results or [] on failure."""
    if not _safe_relation(relation):
        return []
    args = _normalize_args(args)
    if not args or any(not _safe_arg(arg) for arg in args):
        return []
    goal = f"{relation}({', '.join(args)})"
    try:
        results = get_kb().query(pl.Expr(goal))
    except Exception as error:
        print(f"[Prolog ERROR] {error}")
        return []
    if not results or results == [False] or results == ["No"]:
        return []
    return results


def query_yes_no(relation, args):
    """Run a ground boolean query."""
    results = query(relation, args)
    if bool(results) and results != [False] and results != ["No"]:
        return True
    if len(args) == 2 and all(is_safe_atom(normalize_atom(arg)) for arg in args):
        left  = normalize_atom(args[0])
        right = normalize_atom(args[1])
        if right in _values(query(relation, [left,  "X"])):
            return True
        if left  in _values(query(relation, ["X", right])):
            return True
    return False


def _values(raw, var="X"):
    values = []
    for item in raw or []:
        if isinstance(item, dict):
            value = item.get(var, "")
            if value:
                values.append(str(value))
        elif isinstance(item, str) and item.lower() not in {"yes", "no", "false"}:
            values.append(item)
    return values