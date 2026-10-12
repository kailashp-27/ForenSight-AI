"""
backend/modules/plate_postprocess.py
────────────────────────────────────
Accuracy boosters for number-plate OCR that need no model training:

  1. FORMAT-AWARE CORRECTION — a plate has a fixed pattern of letter and
     digit positions (e.g. Indian "TN 09 AB 1234" = LL DD L{1,3} DDDD). An OCR
     engine that reads "TN O9 A8 1234" is fixed by position: the digit slots
     map O→0, the letter slots map 8→B. The fewest-edits parse wins.
  2. MULTI-READ VOTING — the same plate is read from several frames/crops;
     a confidence-weighted per-position vote removes random single-frame errors.

Both are deterministic and explainable: the result carries the individual
reads, the per-position agreement and the number of edits made, so the
final value can always be traced back to what the OCR actually saw.
Pure functions; no I/O.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# OCR confusions: what a *digit* slot most likely was when read as a letter...
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "T": "1", "B": "8",
             "S": "5", "Z": "2", "G": "6", "A": "4"}
# ...and what a *letter* slot most likely was when read as a digit.
_TO_LETTER = {"0": "O", "1": "I", "8": "B", "5": "S", "2": "Z", "6": "G", "4": "A"}

# Visually confusable LETTERS (used to repair an invalid state code).
_LETTER_CONFUSION = {
    "O": "GQDC", "G": "OC", "Q": "OG", "D": "OQ", "C": "GO", "I": "LT", "L": "IT", "T": "IL",
    "B": "RES", "R": "BP", "E": "BF", "S": "BE", "U": "VWO", "V": "UY", "W": "VU", "K": "RX",
    "M": "NH", "N": "MH", "H": "NM", "P": "RF", "F": "PE", "A": "H",
}

# Valid Indian state / UT registration prefixes.
INDIA_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN", "GA", "GJ", "HP", "HR", "JH",
    "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR", "PB", "PY",
    "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB",
}


@dataclass
class PlateParse:
    text: str                 # corrected, no separators, e.g. "TN09AB1234"
    pattern: str              # "IN" | "UK" | "RAW"
    edits: int                # characters changed to satisfy the pattern
    state_valid: Optional[bool] = None


def _fit(s: str, kinds: str) -> Tuple[str, int]:
    """Coerce `s` to a pattern of 'L'/'D' slots; return (text, edits)."""
    out, edits = [], 0
    for ch, kind in zip(s, kinds):
        if kind == "D":
            if ch.isdigit():
                out.append(ch)
            elif ch in _TO_DIGIT:
                out.append(_TO_DIGIT[ch]); edits += 1
            else:
                return s, 99
        else:
            if ch.isalpha():
                out.append(ch)
            elif ch in _TO_LETTER:
                out.append(_TO_LETTER[ch]); edits += 1
            else:
                return s, 99
    return "".join(out), edits


def parse_plate(raw: str) -> PlateParse:
    """Best format-consistent reading of `raw`; falls back to the cleaned string."""
    s = re.sub(r"[^A-Z0-9]", "", raw.upper())
    best: Optional[PlateParse] = None

    # Indian: LL DD L{1,3} DDDD
    for k in (1, 2, 3):
        if len(s) == 4 + k + 4:
            fixed, edits = _fit(s, "LLDD" + "L" * k + "DDDD")
            if edits < 99:
                cand = PlateParse(fixed, "IN", edits, fixed[:2] in INDIA_CODES)
                # Prefer fewer edits, then a valid state code.
                key = (cand.edits, 0 if cand.state_valid else 1)
                if best is None or key < (best.edits, 0 if best.state_valid else 1):
                    best = cand

    # UK: LL DD LLL
    if len(s) == 7:
        fixed, edits = _fit(s, "LLDDLLL")
        if edits < 99 and (best is None or edits < best.edits):
            best = PlateParse(fixed, "UK", edits, None)

    if best is not None and best.pattern == "IN" and best.state_valid is False:
        best = _repair_state(best)

    return best or PlateParse(s, "RAW", 0, None)


def _repair_state(p: PlateParse) -> PlateParse:
    """
    The state prefix is a free checksum: if it is not a real code but exactly
    ONE single-letter confusable swap yields a real one, apply it. Ambiguity
    (zero or several valid swaps) leaves the reading untouched.
    """
    code = p.text[:2]
    fixes = set()
    for pos in (0, 1):
        for alt in _LETTER_CONFUSION.get(code[pos], ""):
            cand = code[:pos] + alt + code[pos + 1:]
            if cand in INDIA_CODES:
                fixes.add(cand)
    if len(fixes) == 1:
        new = fixes.pop()
        return PlateParse(new + p.text[2:], "IN", p.edits + 1, True)
    return p


@dataclass
class VoteResult:
    text: str
    pattern: str
    confidence: float          # 0-1: agreement x mean read confidence
    n_reads: int
    agreement: float           # mean per-position share of the winning character
    edits: int
    state_valid: Optional[bool]
    reads: List[Tuple[str, float]] = field(default_factory=list)


def vote(reads: Sequence[Tuple[str, float]]) -> Optional[VoteResult]:
    """
    Combine several OCR reads of the SAME plate.

    Reads of different lengths are voted separately; the length with the most
    total confidence wins. Each read is first format-corrected so that a
    single bad character doesn't split the vote.
    """
    cleaned = []
    for text, conf in reads:
        p = parse_plate(text)
        if len(p.text) >= 5:
            cleaned.append((p.text, float(conf), p))
    if not cleaned:
        return None

    by_len: Dict[int, List[Tuple[str, float]]] = defaultdict(list)
    for text, conf, _ in cleaned:
        by_len[len(text)].append((text, conf))
    length = max(by_len, key=lambda n: (sum(c for _, c in by_len[n]), n))
    group = by_len[length]

    chars, shares = [], []
    for pos in range(length):
        tally: Dict[str, float] = defaultdict(float)
        for text, conf in group:
            tally[text[pos]] += max(conf, 0.05)
        winner = max(tally, key=tally.get)
        chars.append(winner)
        shares.append(tally[winner] / sum(tally.values()))

    voted = "".join(chars)
    final = parse_plate(voted)           # re-apply format rules to the consensus
    mean_conf = sum(c for _, c in group) / len(group)
    agreement = sum(shares) / len(shares)
    # Single read: agreement is trivially 1, so discount by the read count.
    support = min(1.0, 0.55 + 0.15 * len(group))
    # Raw OCR confidence is often LOW for the right answer on degraded footage, so
    # it only modulates the score; agreement between reads carries more weight.
    confidence = round(min(0.99, agreement * (0.5 + 0.5 * mean_conf) * support
                           * (1.0 if final.state_valid in (None, True) else 0.85)
                           * (1.0 if final.pattern != "RAW" else 0.5)), 3)
    return VoteResult(
        text=final.text, pattern=final.pattern, confidence=confidence, n_reads=len(group),
        agreement=round(agreement, 3), edits=final.edits, state_valid=final.state_valid,
        reads=[(t, round(c, 2)) for t, c in group],
    )


def cluster_reads(reads: Sequence[Tuple[str, float]], threshold: int = 78) -> List[List[Tuple[str, float]]]:
    """Group plate reads that plausibly come from the same plate (string similarity)."""
    from rapidfuzz import fuzz

    clusters: List[List[Tuple[str, float]]] = []
    for text, conf in reads:
        key = re.sub(r"[^A-Z0-9]", "", text.upper())
        placed = False
        for cl in clusters:
            ref = re.sub(r"[^A-Z0-9]", "", cl[0][0].upper())
            if abs(len(ref) - len(key)) <= 1 and fuzz.ratio(ref, key) >= threshold:
                cl.append((text, conf))
                placed = True
                break
        if not placed:
            clusters.append([(text, conf)])
    return clusters
