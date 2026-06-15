# AIML loader - loads BOTH family.aiml (queries) and collect.aiml (data entry)

import os
import re

import aiml


_kernel = None


def load_aiml():
    """Bootstrap the AIML kernel with both AIML files."""
    global _kernel

    base_dir = os.path.dirname(__file__)
    family_aiml  = os.path.join(base_dir, "family.aiml")
    collect_aiml = os.path.join(base_dir, "collect.aiml")   # A2: new file

    _kernel = aiml.Kernel()
    _kernel.setTextEncoding(None)
    _kernel.learn(family_aiml)
    _kernel.learn(collect_aiml)                              # A2: load collect
    print("[AIML] family.aiml and collect.aiml loaded successfully.")
    return _kernel


def get_kernel():
    global _kernel
    if _kernel is None:
        load_aiml()
    return _kernel


def _aiml_text(user_input):
    """Normalize user input for AIML pattern matching."""
    text = user_input.strip().upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)   # remove punctuation (hyphens too)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_aiml_response(user_input):
    """Return AIML response string, or '' when nothing matched."""
    response = get_kernel().respond(_aiml_text(user_input))
    return response.strip() if response else ""


# A2: Read a stored AIML predicate variable from the current session
def get_predicate(name):
    """
    Retrieve a value stored by <set name="..."> during the AIML conversation.
    Uses python-aiml's default session 'LocalSub'.
    Returns '' if the predicate is not set.
    """
    try:
        value = get_kernel().getPredicate(name)
        return value.strip() if value else ""
    except Exception:
        return ""