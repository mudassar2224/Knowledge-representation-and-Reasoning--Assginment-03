# Shared helper functions used by the family chatbot.

import re


KNOWN_NAMES = {
    "ali", "asad", "shakeel", "zain", "hamza", "usman", "bilal", "tariq",
    "alia", "shakeela", "zaini", "laiba", "sana", "nadia", "rukhsana", "hina",
    "hamid", "salma", "asghar", "farah", "yousuf", "rabia", "amir", "samina",
    "faisal", "hiba",
}


PROPERTY_RELATIONS = {"dob", "occupation", "lives_in", "religion"}


RELATION_LABELS = {
    "dob": "date of birth",
    "lives_in": "city",
    "same_city": "same city member",
    "same_occupation": "same occupation member",
    "same_generation": "same generation member",
    "father_in_law": "father-in-law",
    "mother_in_law": "mother-in-law",
    "brother_in_law": "brother-in-law",
    "sister_in_law": "sister-in-law",
    "son_in_law": "son-in-law",
    "daughter_in_law": "daughter-in-law",
}


def _pluralize_label(label: str) -> str:
    label = str(label).strip()
    if not label:
        return label

    irregular = {
        "child": "children",
        "grandchild": "grandchildren",
        "person": "people",
        "man": "men",
        "woman": "women",
        "wife": "wives",
        "husband": "husbands",
        "father": "fathers",
        "mother": "mothers",
        "son": "sons",
        "daughter": "daughters",
        "brother": "brothers",
        "sister": "sisters",
        "grandfather": "grandfathers",
        "grandmother": "grandmothers",
        "grandson": "grandsons",
        "granddaughter": "granddaughters",
        "nephew": "nephews",
        "niece": "nieces",
        "cousin": "cousins",
        "spouse": "spouses",
    }
    if label in irregular:
        return irregular[label]

    if label.endswith("-in-law"):
        base = label[:-7]
        return f"{_pluralize_label(base)}-in-law"

    if " " in label:
        parts = label.split()
        parts[-1] = _pluralize_label(parts[-1])
        return " ".join(parts)

    if label.endswith("y") and len(label) > 1 and label[-2] not in "aeiou":
        return label[:-1] + "ies"

    if label.endswith("s"):
        return label

    return label + "s"


# Maps user-typed words or phrases to canonical Prolog relation names.
RELATION_MAP = {
    # Basic family
    "father": "father",
    "dad": "father",
    "daddy": "father",
    "mother": "mother",
    "mom": "mother",
    "mum": "mother",
    "son": "son",
    "sons": "son",
    "daughter": "daughter",
    "daughters": "daughter",
    "child": "child",
    "children": "child",
    "kid": "child",
    "kids": "child",
    "parent": "parent",
    "parents": "parent",
    "husband": "husband",
    "wife": "wife",
    "spouse": "spouse",
    "partner": "spouse",

    # Siblings
    "sibling": "sibling",
    "siblings": "sibling",
    "brother": "brother",
    "brothers": "brother",
    "sister": "sister",
    "sisters": "sister",

    # Grandparents and descendants
    "grandfather": "grandfather",
    "grandpa": "grandfather",
    "grandmother": "grandmother",
    "grandma": "grandmother",
    "grandparent": "grandparent",
    "grandparents": "grandparent",
    "grandchild": "grandchild",
    "grandchildren": "grandchild",
    "grandson": "grandson",
    "granddaughter": "granddaughter",
    "dada": "dada",
    "dadi": "dadi",
    "nana": "nana",
    "nani": "nani",

    # Extended family
    "uncle": "uncle",
    "aunt": "aunt",
    "aunty": "aunt",
    "cousin": "cousin",
    "cousins": "cousin",
    "nephew": "nephew",
    "niece": "niece",

    # Urdu relations
    "chacha": "chacha",
    "phoophi": "phoophi",
    "phuphi": "phoophi",
    "maamu": "maamu",
    "mamu": "maamu",
    "khala": "khala",
    "chachi": "chachi",
    "phuppa": "phuppa",
    "maami": "maami",
    "mami": "maami",
    "khalu": "khalu",

    # In-laws
    "father in law": "father_in_law",
    "father-in-law": "father_in_law",
    "father_in_law": "father_in_law",
    "mother in law": "mother_in_law",
    "mother-in-law": "mother_in_law",
    "mother_in_law": "mother_in_law",
    "brother in law": "brother_in_law",
    "brother-in-law": "brother_in_law",
    "brother_in_law": "brother_in_law",
    "sister in law": "sister_in_law",
    "sister-in-law": "sister_in_law",
    "sister_in_law": "sister_in_law",
    "son in law": "son_in_law",
    "son-in-law": "son_in_law",
    "son_in_law": "son_in_law",
    "daughter in law": "daughter_in_law",
    "daughter-in-law": "daughter_in_law",
    "daughter_in_law": "daughter_in_law",

    # Properties
    "dob": "dob",
    "date of birth": "dob",
    "birth date": "dob",
    "birthday": "dob",
    "born": "dob",
    "occupation": "occupation",
    "job": "occupation",
    "work": "occupation",
    "profession": "occupation",
    "city": "lives_in",
    "location": "lives_in",
    "address": "lives_in",
    "live": "lives_in",
    "lives": "lives_in",
    "living": "lives_in",
    "from": "lives_in",
    "religion": "religion",
    "faith": "religion",

    # Unary / status relations
    "male": "male",
    "males": "male",
    "female": "female",
    "females": "female",
    "married": "spouse",
    "married to": "spouse",
    "family member": "family_member",
    "family members": "family_member",

    # Logical relations
    "ancestor": "ancestor",
    "ancestors": "ancestor",
    "descendant": "descendant",
    "descendants": "descendant",
    "relative": "blood_relative",
    "relatives": "blood_relative",
    "related": "blood_relative",
    "blood relative": "blood_relative",
    "same city": "same_city",
    "same occupation": "same_occupation",
    "same job": "same_occupation",
    "same profession": "same_occupation",
    "same generation": "same_generation",
}


RELATION_NAMES = set(RELATION_MAP.values()) | {
    "male", "female", "married", "different", "family_member"
}


def clean_text(text: str) -> str:
    """Normalize natural-language input for matching."""
    text = text.lower().strip()
    text = text.replace("'", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9_\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text):
    return re.findall(r"[a-z0-9_]+", clean_text(text))


def capitalize_name(name: str) -> str:
    return str(name).strip().replace("_", " ").title()


def normalize_atom(value: str) -> str:
    """Return a safe lowercase Prolog atom candidate."""
    value = clean_text(value).replace(" ", "_")
    return value


def is_safe_atom(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", value))


def is_variable(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9_]*", value))


def format_value(value: str) -> str:
    """Format Prolog atoms for friendly display."""
    value = str(value).strip()
    date_match = re.fullmatch(r"d(\d{4})_(\d{2})_(\d{2})", value)
    if date_match:
        return "-".join(date_match.groups())
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return capitalize_name(value)


def label_for(relation: str) -> str:
    return RELATION_LABELS.get(relation, relation.replace("_", " "))


def format_response(relation, subject, results):
    if not results:
        return f"Sorry, I could not find any {label_for(relation)} for {capitalize_name(subject)}."

    label = label_for(relation)
    plural_label = _pluralize_label(label)
    subject_cap = capitalize_name(subject)
    results_cap = [format_value(r) for r in results]

    if len(results_cap) == 1:
        return f"{subject_cap}'s {label} is {results_cap[0]}."
    return f"{subject_cap}'s {plural_label} are: {', '.join(results_cap)}."


def format_yes_no(relation: str, x: str, y: str, result: bool) -> str:
    label = label_for(relation)
    xc, yc = capitalize_name(x), capitalize_name(y)
    if relation == "blood_relative":
        if result:
            return f"Yes, {xc} and {yc} are blood relatives."
        return f"No, {xc} and {yc} are not blood relatives."
    if result:
        return f"Yes, {xc} is {yc}'s {label}."
    return f"No, {xc} is not {yc}'s {label}."


def extract_names(text):
    found = []
    for word in words(text):
        if word in KNOWN_NAMES and word not in found:
            found.append(word)
    return found


def find_relation(text):
    """Return the canonical relation mentioned in text, preferring phrases."""
    cleaned = clean_text(text)

    phrase_candidates = sorted(
        (key for key in RELATION_MAP if " " in key or "_" in key),
        key=len,
        reverse=True,
    )
    padded = f" {cleaned} "
    for phrase in phrase_candidates:
        normalized_phrase = clean_text(phrase)
        if f" {normalized_phrase} " in padded:
            return RELATION_MAP[phrase]

    for word in words(cleaned):
        if word in RELATION_MAP:
            return RELATION_MAP[word]
    return None
