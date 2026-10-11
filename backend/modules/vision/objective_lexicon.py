"""
backend/modules/vision/objective_lexicon.py
───────────────────────────────────────────
Objective-lexicon enforcement for AI-generated observations.

A forensic assistant must describe, never conclude. The VLM prompt asks for
neutral wording, but prompts are not a guarantee — this module is the
deterministic backstop applied to every model output before it is stored or
shown.

  "blood"        → "red fluid stain"
  "murder weapon"→ "metallic tool"
  "suspect"      → "person"

Terms that assert legal status or intent have no neutral equivalent and are
replaced with an explicit marker rather than silently dropped, so a reviewer
can see that text was removed.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# Order matters: longer / more specific phrases first.
_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(murder|crime|killing)\s+weapons?\b", re.I), "metallic tool"),
    (re.compile(r"\bweapons?\b", re.I), "object"),
    (re.compile(r"\bbloody\b", re.I), "red-stained"),
    (re.compile(r"\bblood[\s-]?stain(ed)?\b", re.I), "red fluid stain"),
    (re.compile(r"\bblood\b", re.I), "red fluid stain"),
    (re.compile(
        r"\b(suspects?|perpetrators?|criminals?|culprits?|offenders?|killers?|"
        r"murderers?|assailants?|attackers?|thieves|thief|robbers?|burglars?|"
        r"intruders?|victims?)\b", re.I), "person"),
    (re.compile(r"\barmed\b", re.I), "carrying an object"),
    (re.compile(r"\b(guilty|guilt|innocent|innocence)\b", re.I),
     "[removed: conclusory term]"),
    (re.compile(
        r"\b(murder(ed|ing)?|stabb(ed|ing)|shoot(ing)?|shot dead|robb(ery|ing)|"
        r"theft|stolen|assault(ed|ing)?|burglary|homicide|arson|kidnap(ping|ped)?)\b",
        re.I), "[removed: legal characterization]"),
]


def enforce_objective_lexicon(text: str) -> Tuple[str, bool]:
    """
    Rewrite `text` into objective wording.

    Returns (clean_text, was_compliant). `was_compliant` is True only when the
    input needed no rewriting.
    """
    if not text:
        return text, True

    clean = text
    changed = False
    for pattern, replacement in _RULES:
        clean, n = pattern.subn(replacement, clean)
        if n:
            changed = True
    return clean, not changed


def enforce_many(items: List[str]) -> Tuple[List[str], bool]:
    """Apply the lexicon to a list; compliant only if every item was."""
    cleaned: List[str] = []
    compliant = True
    for item in items:
        text, ok = enforce_objective_lexicon(item)
        cleaned.append(text)
        compliant = compliant and ok
    return cleaned, compliant
