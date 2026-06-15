# fact_builder.py
# Converts AIML-collected data into Prolog facts and appends to family_kb.pl

import os
import re

KB_PATH = os.path.join(os.path.dirname(__file__), "family_kb.pl")


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _get_existing_people():
    """
    Scan family_kb.pl for male/female facts to find who is already in the KB.
    Returns a list of lowercase atom strings e.g. ['ali', 'alia', 'shakeel'].
    """
    people = []
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                m = re.match(r"^(?:male|female)\((\w+)\)\.$", line)
                if m:
                    people.append(m.group(1))
    except FileNotFoundError:
        pass
    return people


def _valid_atom(value):
    """Return True if value is a safe lowercase Prolog atom."""
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", value))


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def person_exists(name):
    """Check if a person already has facts in the KB."""
    return name.lower().strip() in _get_existing_people()


def build_facts(data):
    """
    Convert a collected data dict into Prolog fact strings.

    Expected dict keys (all strings, 'unknown' means skip):
        name, gender, father, mother, dob, city, occupation, religion, spouse

    DOB arrives as 'YYYY MM DD' (spaces) because _aiml_text() removes hyphens.
    This function converts it back to the Prolog atom format: d2000_05_12

    Returns a list of Prolog fact strings, each ending with '.'
    """
    name = data.get("name", "").lower().strip()
    if not name or not _valid_atom(name):
        return []

    facts = []
    existing = _get_existing_people()

    # ── Gender ──────────────────────────────
    gender = data.get("gender", "").lower().strip()
    if gender in ("male", "female"):
        facts.append(f"{gender}({name}).")

    # ── Parent facts ─────────────────────────
    father = data.get("father", "unknown").lower().strip()
    if father and father != "unknown" and _valid_atom(father):
        facts.append(f"parent({father}, {name}).")

    mother = data.get("mother", "unknown").lower().strip()
    if mother and mother != "unknown" and _valid_atom(mother):
        facts.append(f"parent({mother}, {name}).")

    # ── Date of birth ────────────────────────
    # AIML input: "2000-05-12" → _aiml_text() → "2000 05 12" (spaces)
    # We convert "2000 05 12" → "2000-05-12" → Prolog atom "d2000_05_12"
    dob_raw = data.get("dob", "unknown").strip()
    if dob_raw.upper() != "UNKNOWN" and dob_raw:
        dob_clean = re.sub(r"\s+", "-", dob_raw)          # spaces → hyphens
        dob_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", dob_clean)
        if dob_match:
            y, mo, d = dob_match.groups()
            facts.append(f"dob({name}, d{y}_{mo}_{d}).")

    # ── City ─────────────────────────────────
    city = data.get("city", "unknown").lower().strip()
    if city and city != "unknown" and _valid_atom(city):
        facts.append(f"lives_in({name}, {city}).")

    # ── Occupation ───────────────────────────
    occupation = data.get("occupation", "unknown").lower().strip()
    if occupation and occupation != "unknown" and _valid_atom(occupation):
        facts.append(f"occupation({name}, {occupation}).")

    # ── Religion ─────────────────────────────
    religion = data.get("religion", "unknown").lower().strip()
    if religion and religion != "unknown" and _valid_atom(religion):
        facts.append(f"religion({name}, {religion}).")

    # ── Spouse / married ─────────────────────
    # married(Husband, Wife) — use gender to determine argument order
    spouse = data.get("spouse", "unknown").lower().strip()
    if spouse and spouse != "unknown" and _valid_atom(spouse):
        if gender == "male":
            facts.append(f"married({name}, {spouse}).")
        else:
            facts.append(f"married({spouse}, {name}).")

    # ── different/2 facts ────────────────────
    # Required for sibling/cousin rules that use different(X, Y)
    # Add new person vs every existing person (both directions)
    for person in existing:
        if person != name:
            facts.append(f"different({name}, {person}).")
            facts.append(f"different({person}, {name}).")

    return facts


def save_facts_to_kb(facts):
    """
    Append Prolog fact strings to family_kb.pl using file handling.
    Returns True on success, False on failure.
    """
    if not facts:
        return False
    try:
        with open(KB_PATH, "a", encoding="utf-8") as f:
            f.write("\n% === Dynamically added fact ===\n")
            for fact in facts:
                f.write(fact + "\n")
        print(f"[FactBuilder] Wrote {len(facts)} facts to family_kb.pl.")
        return True
    except IOError as e:
        print(f"[FactBuilder ERROR] {e}")
        return False