# Natural-language dispatcher - A2 adds dynamic fact collection routing

import re

from aiml_bot import get_aiml_response
from prolog_engine import query, query_yes_no
from utils import (
    KNOWN_NAMES,
    PROPERTY_RELATIONS,
    RELATION_MAP,
    RELATION_NAMES,
    capitalize_name,
    clean_text,
    extract_names,
    find_relation,
    format_response,
    format_value,
    format_yes_no,
    is_safe_atom,
    label_for,
    normalize_atom,
    words,
)


# ── A1: unchanged ────────────────────────────────────────────────────────────
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


# ── A2: collection state ──────────────────────────────────────────────────────
_collecting = False   # True while AIML is gathering data for a new person

# Phrases that trigger data-collection mode
_ADD_TRIGGERS = {
    "add person", "add member", "add new person", "add new member",
    "new person", "new member", "add family member", "add new family member",
}

# Also catch natural-language variations like "I want to add a person"
_ADD_RE = re.compile(
    r"\b(add|create|register|insert|new)\b.{0,25}\b(person|member|family member)\b"
)


# ── Main dispatcher ──────────────────────────────────────────────────────────
def handle_input(user_input):
    global _collecting

    user_input = user_input.strip()
    if not user_input:
        return "Please type a question."

    cleaned = clean_text(user_input)

    # ── Cancel mid-collection ────────────────────────────────────────────────
    if _collecting and cleaned in {"cancel", "stop", "exit"}:
        _collecting = False
        return "Data collection cancelled. The knowledge base was not modified."

    # ── Detect add-person trigger ────────────────────────────────────────────
    if cleaned in _ADD_TRIGGERS or bool(_ADD_RE.search(cleaned)):
        _collecting = True
        response = get_aiml_response(user_input)
        if response:
            return response
        _collecting = False
        return (
            "Could not start data collection. "
            "Make sure collect.aiml is in the project folder and loaded."
        )

    # ── In-progress collection: all input goes to AIML ───────────────────────
    if _collecting:
        response = get_aiml_response(user_input)
        if response:
            if "FACTS_READY" in response:
                _collecting = False
                return _handle_facts_ready()      # A2: build + save facts
            return response
        return "Please answer the question above, or type 'cancel' to stop."

    # ── Normal A1 flow ────────────────────────────────────────────────────────
    if _is_aiml_intent(user_input):
        response = get_aiml_response(user_input)
        if response:
            return response

    return _prolog_dispatch(user_input)


# ── A2: Build and save facts when collection is complete ─────────────────────
def _handle_facts_ready():
    """
    Called when collect.aiml signals FACTS_READY.
    Steps:
      1. Read all 9 predicates from the AIML kernel
      2. Build Prolog fact strings (string handling)
      3. Append to family_kb.pl (file handling)
      4. Reload the KB so new facts are immediately queryable
    """
    from aiml_bot import get_predicate          # avoids circular import at top
    from fact_builder import build_facts, save_facts_to_kb, person_exists
    from prolog_engine import reload_kb

    # Step 1 – fetch AIML variables
    data = {
        "name":       get_predicate("new_name"),
        "gender":     get_predicate("new_gender"),
        "father":     get_predicate("new_father"),
        "mother":     get_predicate("new_mother"),
        "dob":        get_predicate("new_dob"),
        "city":       get_predicate("new_city"),
        "occupation": get_predicate("new_occupation"),
        "religion":   get_predicate("new_religion"),
        "spouse":     get_predicate("new_spouse"),
    }

    name = data["name"].strip().lower()

    if not name:
        return "Error: Name was not captured. Please try 'add person' again."

    if person_exists(name):
        return (
            f"{capitalize_name(name)} already exists in the knowledge base. "
            f"Try querying: tell me about {capitalize_name(name)}"
        )

    # Step 2 – string handling: build Prolog fact strings
    facts = build_facts(data)
    if not facts:
        return (
            "Error: Could not create valid Prolog facts from the collected data. "
            "Check that the name contains only letters and try again."
        )

    # Step 3 – file handling: write to family_kb.pl
    if not save_facts_to_kb(facts):
        return "Error: Could not write to family_kb.pl. Please try again."

    # Step 4 – reload KB (also updates utils.KNOWN_NAMES)
    reload_kb()

    # Also update chatbot-level city and occupation sets
    city = data["city"].strip().lower()
    occupation = data["occupation"].strip().lower()
    if city and city != "unknown":
        KNOWN_CITIES.add(city)
    if occupation and occupation != "unknown":
        KNOWN_OCCUPATIONS.add(occupation)

    main_facts = [f for f in facts if not f.startswith("different")]

    return (
        f"Successfully added {capitalize_name(name)} to the family knowledge base!\n"
        f"Saved {len(main_facts)} facts to family_kb.pl.\n"
        f"You can now query:\n"
        f"  tell me about {capitalize_name(name)}\n"
        f"  who is {capitalize_name(name)}'s father?\n"
        f"  what is {capitalize_name(name)}'s occupation?"
    )


# ── All functions below are UNCHANGED from A1 ─────────────────────────────────

def _is_aiml_intent(text):
    cleaned = clean_text(text)
    return any(re.match(pattern, cleaned, re.IGNORECASE) for pattern in AIML_ONLY_PATTERNS)


def _dedupe(raw, var="X"):
    seen = set()
    values = []
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
                "I can only describe family members that exist in the knowledge base. "
                "Type 'add person' to add a new member first."
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
            missing = [capitalize_name(name) for name in (x, y) if name not in KNOWN_NAMES]
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
            return (f"Yes, {capitalize_name(person)} has {label_for(relation)}." if results
                    else f"No, I could not find any {label_for(relation)} for {capitalize_name(person)}.")
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
        return (f"Yes, {capitalize_name(person)} lives in {format_value(value)}." if result
                else f"No, {capitalize_name(person)} does not live in {format_value(value)}.")
    if label == "from":
        return (f"Yes, {capitalize_name(person)} is from {format_value(value)}." if result
                else f"No, {capitalize_name(person)} is not from {format_value(value)}.")
    if label == "a":
        v = format_value(value).lower()
        return (f"Yes, {capitalize_name(person)} is a {v}." if result
                else f"No, {capitalize_name(person)} is not a {v}.")
    return (f"Yes, {capitalize_name(person)} is {label} {format_value(value)}." if result
            else f"No, {capitalize_name(person)} is not {label} {format_value(value)}.")


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
            return f"No {gender} family members found."
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
            lines.append(f"- {label}: {', '.join(format_value(item) for item in results)}")

    add("Father",       "father",      ["X", person])
    add("Mother",       "mother",      ["X", person])
    add("Spouse",       "spouse",      ["X", person])
    add("Children",     "child",       ["X", person])
    add("Siblings",     "sibling",     ["X", person])
    add("Grandparents", "grandparent", ["X", person])
    add("Date of birth","dob",         [person, "X"])
    add("Occupation",   "occupation",  [person, "X"])
    add("City",         "lives_in",    [person, "X"])
    add("Religion",     "religion",    [person, "X"])

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
        "- add person                    ← add a new family member\n"
        "- who is Ali's father?\n"
        "- tell me about Ali\n"
        "- is Shakeel an ancestor of Zain?\n"
        "- who lives in Lahore?\n"
        "- list all members\n\n"
        "The KB is empty until you add people via 'add person'."
    )