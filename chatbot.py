# chatbot.py
# A2: Data collection now uses a Python state machine instead of AIML <that>.
# This is reliable in both console and Streamlit.

import re

from aiml_bot import get_aiml_response
from prolog_engine import query, query_yes_no
from utils import (
    KNOWN_NAMES, PROPERTY_RELATIONS, RELATION_MAP, RELATION_NAMES,
    capitalize_name, clean_text, extract_names, find_relation,
    format_response, format_value, format_yes_no, is_safe_atom,
    label_for, normalize_atom, words,
)

# ── A1: unchanged constants ───────────────────────────────────────────────────
AIML_ONLY_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|good afternoon|salam|assalam o alaikum)$",
    r"^(bye|goodbye|see you|take care|Allah hafiz|allah hafiz)$",
    r"^(help|what can you do|how do i use this|how do i use)$",
]
KNOWN_CITIES = {"lahore", "karachi", "islamabad", "peshawar"}
KNOWN_OCCUPATIONS = {
    "doctor", "teacher", "engineer", "nurse", "lawyer", "accountant",
    "businessman", "professor", "principal", "pilot", "student",
}
UNARY_RELATIONS = {"male", "female"}


# ═══════════════════════════════════════════════════════════════════════════════
# A2 — PYTHON STATE MACHINE FOR DATA COLLECTION
# ═══════════════════════════════════════════════════════════════════════════════
# Module-level variables hold the collection state.
# In Streamlit, ask_bot() in streamlit_app.py syncs these
# with st.session_state before and after every call to handle_input().
# In the console, they persist naturally for the lifetime of the process.

_collecting: bool = False
_stage: int       = 0       # 1..9 while collecting, 0 when idle
_data: dict       = {}      # accumulates collected field values

_ADD_TRIGGERS = {
    "add person", "add member", "add new person", "add new member",
    "new person", "new member", "add family member", "add new family member",
}
_ADD_RE = re.compile(
    r"\b(add|create|register|insert)\b.{0,30}\b(person|member|family member)\b"
)

# Maps stage number → key in _data dict
COLLECTION_KEYS = {
    1: "name",
    2: "gender",
    3: "father",
    4: "mother",
    5: "dob",
    6: "city",
    7: "occupation",
    8: "religion",
    9: "spouse",
}


def _prompt(stage: int) -> str:
    """Return the bot's question for the given stage."""
    name = _data.get("name", "the person").replace("_", " ").title()
    prompts = {
        1: (
            "Step 1/9 — Name\n"
            "Enter the person's name (one word, letters only, e.g. ali):"
        ),
        2: (
            f"Step 2/9 — Gender\n"
            f"Is {name} male or female?  (type: male  or  female)"
        ),
        3: (
            f"Step 3/9 — Father\n"
            f"Enter {name}'s father's name, or type  unknown:"
        ),
        4: (
            f"Step 4/9 — Mother\n"
            f"Enter {name}'s mother's name, or type  unknown:"
        ),
        5: (
            f"Step 5/9 — Date of birth\n"
            f"Enter {name}'s DOB as YYYY-MM-DD (e.g. 2000-05-12), or type  unknown:"
        ),
        6: (
            f"Step 6/9 — City\n"
            f"Enter the city where {name} lives, or type  unknown:"
        ),
        7: (
            f"Step 7/9 — Occupation\n"
            f"Enter {name}'s occupation, or type  unknown:"
        ),
        8: (
            f"Step 8/9 — Religion\n"
            f"Enter {name}'s religion, or type  unknown:"
        ),
        9: (
            f"Step 9/9 — Spouse\n"
            f"Enter {name}'s spouse's name, or type  unknown:"
        ),
    }
    return prompts[stage]


def _validate_step(stage: int, raw: str):
    """
    Validate user input for a collection stage.
    Returns (is_valid: bool, cleaned_value_or_error_msg: str)
    """
    value = raw.strip()

    if value.lower() == "unknown":
        return True, "unknown"

    if stage == 1:  # Name must be a safe Prolog atom
        atom = value.lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", atom):
            return False, (
                "Name must start with a letter and contain only "
                "letters, digits, or underscores (e.g.  ali  or  ali_hassan)."
            )
        return True, atom

    if stage == 2:  # Gender
        g = value.lower()
        if g not in ("male", "female"):
            return False, "Please type exactly  male  or  female."
        return True, g

    if stage == 5:  # DOB — accept YYYY-MM-DD or YYYY MM DD
        dob = re.sub(r"[\s\-]+", "-", value)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
            return False, (
                "Please enter the date as YYYY-MM-DD (e.g. 2000-05-12) "
                "or type  unknown."
            )
        return True, dob

    # All other stages — just lowercase and strip
    cleaned = value.lower().strip()
    if not cleaned:
        return False, "Please enter a value or type  unknown."
    return True, cleaned


def _process_collection_step(user_input: str) -> str:
    """
    Validate and store one answer, then advance to the next stage.
    Called by handle_input() whenever _collecting is True.
    """
    global _collecting, _stage, _data

    key = COLLECTION_KEYS[_stage]
    is_valid, result = _validate_step(_stage, user_input)

    if not is_valid:
        # Re-show the same prompt with an error message
        return f"⚠  {result}\n\n{_prompt(_stage)}"

    # Store in Python dict
    _data[key] = result

    # Also push to AIML predicate (satisfies assignment step 4)
    try:
        from aiml_bot import set_predicate
        set_predicate(f"new_{key}", result)
    except Exception:
        pass

    # Advance stage
    _stage += 1

    if _stage > 9:
        # All 9 fields collected — build and save facts
        _collecting = False
        _stage = 0
        return _handle_facts_ready()

    return _prompt(_stage)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def handle_input(user_input: str) -> str:
    global _collecting, _stage, _data

    user_input = user_input.strip()
    if not user_input:
        return "Please type a question."

    cleaned = clean_text(user_input)

    # ── Cancel collection ────────────────────────────────────────────────────
    if _collecting and cleaned in {"cancel", "stop", "exit"}:
        _collecting = False
        _stage = 0
        _data = {}
        return "Data collection cancelled. The knowledge base was not modified."

    # ── "add person" typed while already collecting → restart ────────────────
    if _collecting and (cleaned in _ADD_TRIGGERS or bool(_ADD_RE.search(cleaned))):
        _stage = 1
        _data = {}
        return "Restarting data collection.\n\n" + _prompt(1)

    # ── Start new collection ─────────────────────────────────────────────────
    if not _collecting and (cleaned in _ADD_TRIGGERS or bool(_ADD_RE.search(cleaned))):
        _collecting = True
        _stage = 1
        _data = {}
        return "Starting data collection for a new family member.\n\n" + _prompt(1)

    # ── In-progress: Python handles EVERYTHING — AIML is NOT called ──────────
    # This avoids the family.aiml pattern-matching interference and the
    # unreliable <that> context tracking that broke Streamlit collection.
    if _collecting:
        return _process_collection_step(user_input)

    # ── Normal A1 flow ────────────────────────────────────────────────────────
    if _is_aiml_intent(user_input):
        response = get_aiml_response(user_input)
        if response:
            return response

    return _prolog_dispatch(user_input)


# ── A2: called when all 9 steps are done ─────────────────────────────────────

def _handle_facts_ready() -> str:
    """Steps 3-6 of the assignment: build facts, write file, reload KB."""
    from fact_builder import build_facts, save_facts_to_kb, person_exists
    from prolog_engine import reload_kb

    data = _data.copy()
    name = data.get("name", "").strip().lower()

    if not name:
        return "Error: Name was not captured. Please try 'add person' again."

    if person_exists(name):
        return (
            f"{capitalize_name(name)} already exists in the knowledge base.\n"
            f"Try: tell me about {capitalize_name(name)}"
        )

    # Step 3: string handling — build Prolog fact strings
    facts = build_facts(data)
    if not facts:
        return "Error: Could not create valid Prolog facts. Please try 'add person' again."

    # Step 4: file handling — append to family_kb.pl
    if not save_facts_to_kb(facts):
        return "Error: Could not write to family_kb.pl. Please try again."

    # Step 5: reload KB (also updates utils.KNOWN_NAMES via reload_kb)
    reload_kb()

    # Keep in-memory city/occupation sets in sync
    city       = data.get("city", "unknown").lower()
    occupation = data.get("occupation", "unknown").lower()
    if city and city != "unknown":
        KNOWN_CITIES.add(city)
    if occupation and occupation != "unknown":
        KNOWN_OCCUPATIONS.add(occupation)

    main_facts = [f for f in facts if not f.startswith("different")]
    return (
        f"Successfully added {capitalize_name(name)} to the family knowledge base!\n"
        f"Saved {len(main_facts)} facts to family_kb.pl.\n\n"
        f"You can now query:\n"
        f"  tell me about {capitalize_name(name)}\n"
        f"  who is {capitalize_name(name)}'s father?\n"
        f"  what is {capitalize_name(name)}'s occupation?"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# A1 FUNCTIONS — UNCHANGED FROM ASSIGNMENT 1
# ═══════════════════════════════════════════════════════════════════════════════

def _is_aiml_intent(text):
    cleaned = clean_text(text)
    return any(re.match(p, cleaned, re.IGNORECASE) for p in AIML_ONLY_PATTERNS)


def _dedupe(raw, var="X"):
    seen, values = set(), []
    for item in raw or []:
        value = ""
        if isinstance(item, dict):
            value = item.get(var, "")
            if not value and item:
                value = next(iter(item.values()))
        elif isinstance(item, str) and item.lower() not in {"yes", "no", "false"}:
            value = item
        value = str(value).strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _prolog_dispatch(text):
    cleaned = clean_text(text)
    if not cleaned:
        return "Please type a question."

    names = extract_names(cleaned)

    yes_no = _answer_yes_no(cleaned, names)
    if yes_no:
        return yes_no

    unary_status = _answer_unary_status(cleaned)
    if unary_status:
        return unary_status

    gender_list = _answer_gender_list(cleaned)
    if gender_list:
        return gender_list

    occupation_answer = _answer_occupation_list(cleaned)
    if occupation_answer:
        return occupation_answer

    family_list = _answer_family_member_list(cleaned)
    if family_list:
        return family_list

    if _looks_like_profile_request(cleaned) and names:
        return _all_about(names[0])

    relation = find_relation(cleaned)

    if relation in PROPERTY_RELATIONS and names:
        return _answer_property(relation, names[0])

    if relation and relation in RELATION_NAMES and names:
        return _answer_relationship(relation, names[0])

    grouped_answer = _answer_same_group(cleaned, names)
    if grouped_answer:
        return grouped_answer

    city_answer = _answer_city_list(cleaned)
    if city_answer:
        return city_answer

    all_members = _answer_all_members(cleaned)
    if all_members:
        return all_members

    unknown_name_answer = _answer_unknown_name_question(cleaned)
    if unknown_name_answer:
        return unknown_name_answer

    if _looks_like_profile_request(cleaned) and not names:
        if re.search(r"\b(someone|someone else|person|member|not in the family|not in this family)\b", cleaned):
            return (
                "I can only describe family members in the knowledge base. "
                "Type 'add person' to add a new member."
            )

    if len(names) == 1:
        return _all_about(names[0])

    return _fallback()


def _answer_yes_no(text, names):
    m = re.search(r"\bis\s+(\w+)\s+(?:a|an|the)?\s*(.+?)\s+(?:of|to|for)\s+(\w+)\b", text)
    if m:
        x = normalize_atom(m.group(1))
        relation = find_relation(m.group(2))
        y = normalize_atom(m.group(3))
        if relation in RELATION_NAMES:
            missing = [capitalize_name(n) for n in (x, y) if n not in KNOWN_NAMES]
            if missing:
                return f"Sorry, I do not have {', '.join(missing)} in this family KB."
            if _valid_person_pair(x, y):
                return format_yes_no(relation, x, y, query_yes_no(relation, [x, y]))

    m = re.search(r"\bis\s+(\w+)\s+(?:a|an\s+)?(male|female)\b", text)
    if m:
        person = normalize_atom(m.group(1))
        relation = normalize_atom(m.group(2))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        result = bool(query(relation, [person]))
        return (f"Yes, {capitalize_name(person)} is {relation}."
                if result else f"No, {capitalize_name(person)} is not {relation}.")

    m = re.search(r"\bis\s+(\w+)\s+married\b(?!\s+(?:to|with|for))", text)
    if m:
        person = normalize_atom(m.group(1))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        result = bool(query("spouse", [person, "X"])) or bool(query("married", [person, "X"]))
        return (f"Yes, {capitalize_name(person)} is married."
                if result else f"No, {capitalize_name(person)} is not married.")

    m = re.search(r"\bare\s+(\w+)\s+and\s+(\w+)\s+married\b", text)
    if m:
        x, y = normalize_atom(m.group(1)), normalize_atom(m.group(2))
        missing = [capitalize_name(n) for n in (x, y) if n not in KNOWN_NAMES]
        if missing:
            return f"Sorry, I do not have {', '.join(missing)} in this family KB."
        if _valid_person_pair(x, y):
            return format_yes_no("spouse", x, y, query_yes_no("spouse", [x, y]))

    m = re.search(r"\bis\s+(\w+)\s+related\s+to\s+(\w+)\b", text)
    if m:
        x, y = normalize_atom(m.group(1)), normalize_atom(m.group(2))
        missing = [capitalize_name(n) for n in (x, y) if n not in KNOWN_NAMES]
        if missing:
            return f"Sorry, I do not have {', '.join(missing)} in this family KB."
        if _valid_person_pair(x, y):
            return format_yes_no("blood_relative", x, y, query_yes_no("blood_relative", [x, y]))

    m = re.search(r"\b(?:are|re)\s+(\w+)\s+and\s+(\w+)\s+(?:related|blood relatives|relatives)\b", text)
    if m:
        x, y = normalize_atom(m.group(1)), normalize_atom(m.group(2))
        missing = [capitalize_name(n) for n in (x, y) if n not in KNOWN_NAMES]
        if missing:
            return f"Sorry, I do not have {', '.join(missing)} in this family KB."
        if _valid_person_pair(x, y):
            return format_yes_no("blood_relative", x, y, query_yes_no("blood_relative", [x, y]))

    m = re.search(r"\bdoes\s+(\w+)\s+(?:live|lives|reside)\s+(?:in|at)\s+(\w+)\b", text)
    if m:
        person, city = normalize_atom(m.group(1)), normalize_atom(m.group(2))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        if city in KNOWN_CITIES:
            return _property_yes_no("lives in", person, city, query_yes_no("lives_in", [person, city]))

    m = re.search(r"\bis\s+(\w+)\s+from\s+(\w+)\b", text)
    if m:
        person, city = normalize_atom(m.group(1)), normalize_atom(m.group(2))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        if city in KNOWN_CITIES:
            return _property_yes_no("from", person, city, query_yes_no("lives_in", [person, city]))

    m = re.search(r"\bis\s+(\w+)\s+(?:a|an)\s+(\w+)\b", text)
    if m:
        person, occupation = normalize_atom(m.group(1)), _singular(normalize_atom(m.group(2)))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        if occupation in KNOWN_OCCUPATIONS:
            return _property_yes_no("a", person, occupation, query_yes_no("occupation", [person, occupation]))

    m = re.search(r"\bdoes\s+(\w+)\s+have\s+(.+)\b", text)
    if m:
        person = normalize_atom(m.group(1))
        relation = find_relation(m.group(2))
        if person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
        if relation in RELATION_NAMES:
            results = _dedupe(query(relation, ["X", person]))
            return (f"Yes, {capitalize_name(person)} has {label_for(relation)}."
                    if results else
                    f"No, I could not find any {label_for(relation)} for {capitalize_name(person)}.")
    return None


def _answer_unary_status(text):
    m = re.search(r"\bis\s+(\w+)\s+(?:a|an\s+)?(male|female)\b", text)
    if not m:
        return None
    person = normalize_atom(m.group(1))
    relation = normalize_atom(m.group(2))
    if person not in KNOWN_NAMES or relation not in UNARY_RELATIONS:
        return None
    result = bool(query(relation, [person]))
    return (f"Yes, {capitalize_name(person)} is {relation}."
            if result else f"No, {capitalize_name(person)} is not {relation}.")


def _valid_person_pair(x, y):
    return x in KNOWN_NAMES and y in KNOWN_NAMES and is_safe_atom(x) and is_safe_atom(y)


def _property_yes_no(label, person, value, result):
    if label == "lives in":
        return (f"Yes, {capitalize_name(person)} lives in {format_value(value)}."
                if result else f"No, {capitalize_name(person)} does not live in {format_value(value)}.")
    if label == "from":
        return (f"Yes, {capitalize_name(person)} is from {format_value(value)}."
                if result else f"No, {capitalize_name(person)} is not from {format_value(value)}.")
    if label == "a":
        v = format_value(value).lower()
        return (f"Yes, {capitalize_name(person)} is a {v}."
                if result else f"No, {capitalize_name(person)} is not a {v}.")
    return (f"Yes, {capitalize_name(person)} is {label} {format_value(value)}."
            if result else f"No, {capitalize_name(person)} is not {label} {format_value(value)}.")


def _looks_like_profile_request(text):
    return bool(re.search(r"\b(tell me about|about|profile|details|all about|information about)\b", text))


def _answer_city_list(text):
    city = None
    m = re.search(
        r"\b(?:who|which people|people|members|family members|show|list)\b.*\b(?:live|lives|living|from|in)\s+(\w+)\b",
        text)
    if m:
        city = normalize_atom(m.group(1))
    else:
        m = re.search(r"\b(\w+)\s+(?:members|people|family)\b", text)
        if m:
            candidate = normalize_atom(m.group(1))
            if candidate in KNOWN_CITIES:
                city = candidate
    if not city or city not in KNOWN_CITIES:
        return None
    results = _dedupe(query("lives_in", ["X", city]))
    if results:
        return f"Family members in {capitalize_name(city)}: {', '.join(format_value(n) for n in results)}."
    return f"No family members found in {capitalize_name(city)}."


def _answer_gender_list(text):
    if not re.search(r"\b(who|which|list|show)\b", text):
        return None
    for gender in ("male", "female"):
        if re.search(rf"\b{gender}\b", text):
            results = _unique_sorted(_dedupe(query(gender, ["X"])))
            if results:
                return f"{gender.capitalize()} family members: {', '.join(format_value(n) for n in results)}."
            return f"No {gender} family members found. Type 'add person' to add members."
    return None


def _answer_family_member_list(text):
    if not re.search(r"\b(who|which|list|show|all|everyone)\b", text):
        return None
    if not re.search(r"\b(members?|people|everyone|all members|all people|family kb|family knowledge base|family members?)\b", text):
        return None
    if re.search(r"\b(male|female)\b", text):
        return None
    members = _unique_sorted(_dedupe(query("male", ["X"])) + _dedupe(query("female", ["X"])))
    if not members:
        return "No family members found. Type 'add person' to add the first member."
    return "All family members: " + ", ".join(format_value(m) for m in members) + "."


def _answer_all_members(text):
    if not re.search(r"\b(all family|all members|all people|everyone|list family|show family)\b", text):
        return None
    members = _unique_sorted(_dedupe(query("male", ["X"])) + _dedupe(query("female", ["X"])))
    if not members:
        return "No family members found. Type 'add person' to add the first member."
    return "All family members: " + ", ".join(format_value(m) for m in members) + "."


def _answer_same_group(text, names):
    if not names:
        return None
    relation = None
    if "same city" in text:
        relation = "same_city"
    elif "same occupation" in text or "same job" in text or "same profession" in text:
        relation = "same_occupation"
    elif "same generation" in text:
        relation = "same_generation"
    if not relation:
        return None
    results = _dedupe(query(relation, [names[0], "X"]))
    return format_response(relation, names[0], results)


def _answer_occupation_list(text):
    if extract_names(text):
        return None
    if not re.search(r"\b(who|list|show|which)\b", text):
        return None
    for token in words(text):
        occupation = _singular(token)
        if occupation in KNOWN_OCCUPATIONS:
            results = _dedupe(query("occupation", ["X", occupation]))
            if results:
                return f"Family members who are {occupation}s: {', '.join(format_value(n) for n in results)}."
            return f"No family members found with occupation {format_value(occupation)}."
    return None


def _answer_unknown_name_question(text):
    if re.search(r"\bnot in (?:the|this) family\b", text):
        return "I can only describe family members that exist in the knowledge base."
    patterns = (
        r"\b(?:who|what)\s+is\s+(\w+)\s+s\s+(.+)$",
        r"\b(?:who|what)\s+is\s+(\w+)\s+(?:a|an|the)?\s+(.+)$",
        r"\b(?:who|what)\s+are\s+(\w+)\s+s\s+(.+)$",
        r"\b(?:who|what)\s+are\s+(\w+)\s+(?:a|an|the)?\s+(.+)$",
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        person = normalize_atom(m.group(1))
        relation = find_relation(m.group(2))
        if relation and person not in KNOWN_NAMES:
            return f"Sorry, I do not have {capitalize_name(person)} in this family KB."
    return None


def _answer_property(relation, person):
    results = _dedupe(query(relation, [person, "X"]))
    return format_response(relation, person, results)


def _answer_relationship(relation, person):
    results = _dedupe(query(relation, ["X", person]))
    return format_response(relation, person, results)


def _all_about(person):
    if person not in KNOWN_NAMES:
        return (
            f"Sorry, I have no information about {capitalize_name(person)}. "
            f"Type 'add person' to add them to the knowledge base."
        )
    lines = [f"Here is what I know about {capitalize_name(person)}:"]

    def add(label, relation, args):
        results = _dedupe(query(relation, args))
        if results:
            lines.append(f"- {label}: {', '.join(format_value(i) for i in results)}")

    add("Father",        "father",      ["X", person])
    add("Mother",        "mother",      ["X", person])
    add("Spouse",        "spouse",      ["X", person])
    add("Children",      "child",       ["X", person])
    add("Siblings",      "sibling",     ["X", person])
    add("Grandparents",  "grandparent", ["X", person])
    add("Date of birth", "dob",         [person, "X"])
    add("Occupation",    "occupation",  [person, "X"])
    add("City",          "lives_in",    [person, "X"])
    add("Religion",      "religion",    [person, "X"])

    if len(lines) == 1:
        return f"Sorry, I have no information about {capitalize_name(person)}."
    return "\n".join(lines)


def _unique_sorted(values):
    return sorted(set(values), key=lambda v: format_value(v))


def _singular(word):
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _fallback():
    return (
        "I can answer family knowledge-base questions. Try:\n"
        "  add person                 ← add a new family member\n"
        "  who is Ali's father?\n"
        "  tell me about Ali\n"
        "  is Shakeel an ancestor of Zain?\n"
        "  who lives in Lahore?\n"
        "  list all members\n\n"
        "The KB is empty until you add people via 'add person'."
    )