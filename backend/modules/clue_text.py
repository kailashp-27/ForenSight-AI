"""
backend/modules/clue_text.py
────────────────────────────
Pure functions that turn raw text (OCR output, transcripts, PDF text) into
structured CLUES, and normalise clue values so the same real-world token
read from different evidence compares equal.

A clue is an observable token — a number plate, phone number, e-mail, an
alphanumeric identifier, a currency amount. Extraction is rule-based and
explainable: every clue records which pattern produced it and the
surrounding text it came from.

OCR confusions (O/0, I/1, B/8, S/5, Z/2, G/6) are folded in `match_key` so a
plate read as "AB12 CDE" in a photo and "A812 CDE" in CCTV still correlates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

# Ordered most-specific first; a span claimed by an earlier pattern is not
# re-claimed by a later one.
_PATTERNS = [
    # Indian registration: TN 09 AB 1234 / TN09AB1234 / MH-12-DE-1433
    # The series may contain OCR-confused digits (B read as 8, O as 0 ...), so
    # [A-Z0-9] is allowed there provided at least one real letter is present.
    ("PLATE", "plate_in", re.compile(r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?(?=[A-Z0-9]{0,2}[A-Z])[A-Z0-9]{1,3}[\s-]?\d{4}\b")),
    # UK current format: AB12 CDE
    ("PLATE", "plate_uk", re.compile(r"\b[A-Z]{2}\d{2}[\s-]?[A-Z]{3}\b")),
    # Generic 2-3 letters + 3-4 digits: ABC-1234, KA 4821
    # Not when it is just the head of a longer reference such as "FS-2026-001".
    ("PLATE", "plate_generic", re.compile(r"\b[A-Z]{2,3}[\s-]?\d{3,4}\b(?![\s-]?\d)")),
    ("EMAIL", "email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", "phone", re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,11}\d(?![\w])")),
    ("AMOUNT", "amount", re.compile(r"(?:₹|Rs\.?|INR|\$|€|£)\s?\d[\d,]*(?:\.\d{1,2})?")),
]

_CONFUSION = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                            "B": "8", "S": "5", "Z": "2", "G": "6"})


@dataclass(frozen=True)
class TextClue:
    kind: str
    value: str          # as seen (display)
    norm: str           # canonical form for exact comparison
    pattern: str        # which rule produced it
    start: int
    end: int
    context: str        # surrounding text for explainability


def normalize(kind: str, value: str) -> str:
    """Canonical comparison form: upper-case alphanumerics (digits only for phones)."""
    if kind == "PHONE":
        digits = re.sub(r"\D", "", value)
        # Compare on the national significant number (last 10 digits).
        return digits[-10:] if len(digits) >= 10 else digits
    if kind == "EMAIL":
        return value.strip().lower()
    if kind == "AMOUNT":
        return re.sub(r"[^\d.]", "", value)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def match_key(kind: str, norm: str) -> str:
    """Fold common OCR confusions so near-identical OCR reads share a key."""
    if kind in ("PLATE", "ID"):
        return norm.translate(_CONFUSION)
    return norm


def _context(text: str, start: int, end: int, radius: int = 40) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - radius): end + radius]).strip()


# Characters OCR engines emit for letters in noisy plates ("KL 83 ] 9493" = "...J...").
# Same length as the input so match spans/contexts stay aligned.
_SYMBOL_FIX = str.maketrans({"]": "J", "}": "J", "|": "I", "!": "I"})


# "Plate: Tx-882-V", "registration no. KA01AB1234", "vehicle number ..." — the WORD before
# an identifier tells us it is a plate even when its shape is unusual or partly read.
_CUE_RE = re.compile(
    r"(?:number\s*plate|licen[cs]e\s*plate|registration(?:\s*(?:no|number))?|reg\.?\s*no|"
    r"plate(?:\s*(?:no|number))?|vehicle\s*(?:no|number)|\breg\b)\.?\s*[:#\-\u2013]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9 \-]{2,24})", re.I)
_CUE_WORDS = re.compile(r"plate|registration|\breg\b|licen[cs]e|vehicle|number", re.I)
_CUE_FILLER = {"was", "is", "are", "no", "number", "the", "a", "an", "of", "on", "at", "it", "its",
               "reads", "read", "said", "as", "to", "for", "plate", "reg", "registration"}
# Two-letter English words that are not plate prefixes ("to 1400", "at 0930").
_NOT_PLATE_PREFIX = {"TO", "AT", "IN", "ON", "NO", "OF", "BY", "IS", "IT", "AS", "OR", "IF", "SO", "DO",
                     "GO", "BE", "WE", "HE", "ME", "MY", "AN", "AM", "PM", "NR", "ID", "RE", "VS"}


def extract_clues(text: str) -> List[TextClue]:
    """Extract all clues from `text` (deduplicated by kind + normalised value)."""
    if not text or not text.strip():
        return []
    # Only repair symbols that sit between alphanumerics/spaces inside a token.
    text = re.sub(r"(?<=[A-Za-z0-9 ])[\]}|!](?=[A-Za-z0-9 ])", lambda m: m.group(0).translate(_SYMBOL_FIX), text)

    upper = text.upper()
    claimed: List[tuple] = []
    found: Dict[tuple, TextClue] = {}

    def overlaps(a: int, b: int) -> bool:
        return any(a < e and b > s for s, e in claimed)

    # Cue-driven plates first: they win over generic shape matching.
    for m in _CUE_RE.finditer(text):
        tokens = list(re.finditer(r"[A-Za-z0-9]+", m.group(1)))
        while tokens and tokens[0].group(0).lower() in _CUE_FILLER:       # "plate WAS TN09..."
            tokens.pop(0)
        kept = []
        for tk in tokens:
            w = tk.group(0)
            if w.isalpha() and (len(w) > 3 or (len(w) == 3 and w.islower())):   # an ordinary word ends the plate
                break
            kept.append(tk)
        if not kept:
            continue
        s = m.start(1) + kept[0].start()
        e = m.start(1) + kept[-1].end()
        raw = text[s:e]
        norm = normalize("PLATE", raw)
        if re.search(r"[A-Z]", norm) and re.search(r"\d", norm) and 4 <= len(norm) <= 11 and not overlaps(s, e):
            claimed.append((s, e))
            found.setdefault(("PLATE", norm), TextClue("PLATE", raw, norm, "plate_cue", s, e, _context(text, s, e)))

    for kind, name, pattern in _PATTERNS:
        # Plates are matched on upper-cased text (OCR case is unreliable);
        # e-mails keep original case.
        haystack = text if kind in ("EMAIL", "AMOUNT") else upper
        for m in pattern.finditer(haystack):
            s, e = m.span()
            if overlaps(s, e):
                continue
            raw = text[s:e].strip()
            norm = normalize(kind, raw)
            if name == "plate_generic":
                # A bare "AB 1234" is ambiguous: it is a PLATE only with a cue nearby,
                # otherwise it is just an identifier (case ref, camera name ...).
                if re.sub(r"[^A-Z]", "", norm)[:2] in _NOT_PLATE_PREFIX:
                    continue
                if not _CUE_WORDS.search(text[max(0, s - 45):s]):
                    kind_here = "ID"
                    claimed.append((s, e))
                    if len(norm) >= 5:
                        found.setdefault(("ID", norm), TextClue("ID", raw, norm, "alnum_id", s, e, _context(text, s, e)))
                    continue
            if kind == "PHONE" and not (10 <= len(norm) <= 13):
                continue
            if kind == "PLATE":
                # Plates need both letters and digits and a sane length.
                if not (re.search(r"[A-Z]", norm) and re.search(r"\d", norm) and 5 <= len(norm) <= 11):
                    continue
            claimed.append((s, e))
            key = (kind, norm)
            if key not in found:
                found[key] = TextClue(kind, raw, norm, name, s, e, _context(text, s, e))

    # Leftover alphanumeric identifiers (e.g. serial / case / account numbers).
    for m in re.finditer(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9-]{6,20}\b", upper):
        s, e = m.span()
        if overlaps(s, e):
            continue
        norm = normalize("ID", m.group(0))
        key = ("ID", norm)
        if key not in found and len(norm) >= 6:
            found[key] = TextClue("ID", text[s:e], norm, "alnum_id", s, e, _context(text, s, e))

    return sorted(found.values(), key=lambda c: c.start)
