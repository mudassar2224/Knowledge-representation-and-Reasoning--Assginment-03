# AIML loader - loads family.aiml, collect.aiml, and analysis.aiml

import os
import re

import aiml


_kernel = None


def load_aiml():
    """Bootstrap the AIML kernel with all three AIML files."""
    global _kernel

    base_dir = os.path.dirname(__file__)
    family_aiml   = os.path.join(base_dir, "family.aiml")
    collect_aiml  = os.path.join(base_dir, "collect.aiml")
    analysis_aiml = os.path.join(base_dir, "analysis.aiml")   # ← NEW (A3 Priority 1+2)

    _kernel = aiml.Kernel()
    _kernel.setTextEncoding(None)
    _kernel.learn(family_aiml)
    _kernel.learn(collect_aiml)
    _kernel.learn(analysis_aiml)                                # ← NEW
    print("[AIML] family.aiml, collect.aiml, and analysis.aiml loaded successfully.")
    return _kernel


def get_kernel():
    global _kernel
    if _kernel is None:
        load_aiml()
    return _kernel


def _aiml_text(user_input):
    """Normalize user input for AIML pattern matching."""
    text = user_input.strip().upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_aiml_response(user_input):
    """Return AIML response string, or '' when nothing matched."""
    response = get_kernel().respond(_aiml_text(user_input))
    return response.strip() if response else ""


def get_predicate(name):
    try:
        value = get_kernel().getPredicate(name)
        return value.strip() if value else ""
    except Exception:
        return ""


def set_predicate(name: str, value: str):
    try:
        get_kernel().setPredicate(name, value)
    except Exception:
        pass