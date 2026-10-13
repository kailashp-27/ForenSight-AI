"""
backend/modules/clue_terms.py
─────────────────────────────
Free-text clue extraction for speech transcripts, PDF text and VLM notes.

`clue_text.extract_clues` finds rigid patterns (plates, phones, e-mails ...).
Real investigative text is mostly NOT rigid: people are named, vehicles and
items are described. This module adds two more clue kinds so that what is
SAID or WRITTEN can meet what is SEEN:

  NAME    proper-noun sequences ("Ramesh Kumar", "Anna Nagar")
  OBJECT  descriptions of vehicles / items ("white van", "black backpack", "knife")

Everything is rule-based and explainable. `object_key` canonicalises object
descriptions so synonyms line up across sources: speech "white sedan", a YOLO
"white car" and a VLM "white hatchback" all share the key "white car".

Limits (kept visible in the UI/report): rule-based name detection will miss
lower-case names and may pick up place names or titles; matches built from
names are therefore never rated STRONG on their own.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from backend.modules.clue_text import TextClue, _context

COLOURS = {
    "white", "black", "red", "blue", "green", "yellow", "orange", "grey", "gray", "silver",
    "brown", "pink", "purple", "maroon", "golden", "gold", "beige", "cream",
}

# vehicle word -> canonical detector class
VEHICLES: Dict[str, str] = {
    "car": "car", "sedan": "car", "hatchback": "car", "suv": "car", "jeep": "car", "taxi": "car",
    "cab": "car", "hatch": "car", "van": "truck", "truck": "truck", "lorry": "truck",
    "pickup": "truck", "tempo": "truck", "bus": "bus", "bike": "motorcycle",
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "scooter": "motorcycle",
    "scooty": "motorcycle", "bicycle": "bicycle", "cycle": "bicycle",
}

# item word -> canonical item
ITEMS: Dict[str, str] = {
    "knife": "knife", "knives": "knife", "dagger": "knife", "blade": "knife",
    "gun": "gun", "pistol": "gun", "revolver": "gun", "handgun": "gun", "firearm": "gun",
    "backpack": "backpack", "rucksack": "backpack", "bag": "bag", "handbag": "handbag",
    "suitcase": "suitcase", "briefcase": "suitcase", "duffel": "duffel bag",
    "helmet": "helmet", "mask": "mask", "gloves": "gloves", "glove": "gloves",
    "hammer": "hammer", "crowbar": "crowbar", "phone": "cell phone", "mobile": "cell phone",
    "cellphone": "cell phone", "smartphone": "cell phone", "laptop": "laptop",
    "bottle": "bottle", "wallet": "wallet", "camera": "camera", "rope": "rope",
    "stick": "stick", "bat": "bat", "umbrella": "umbrella", "box": "box", "parcel": "box",
}

_STOP_CAPS = {
    "The", "This", "That", "These", "Those", "There", "They", "Then", "Them", "Their", "When",
    "What", "Where", "Which", "Who", "Why", "How", "Yes", "Not", "And", "But", "For", "With",
    "From", "Have", "Has", "Had", "Was", "Were", "Are", "Our", "Your", "His", "Her", "Its",
    "Just", "Okay", "Well", "Please", "Thank", "Thanks", "Sorry", "Hello", "Right", "Also",
    "Because", "After", "Before", "While", "Still", "Maybe", "Today", "Tomorrow", "Yesterday",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "June", "July", "August", "September", "October",
    "November", "December", "Investigator", "Witness", "Statement", "Signed", "Case", "Police",
    "Station", "Officer", "Sir", "Madam", "Mister", "Question", "Answer", "Interview", "Report",
    "Page", "Evidence", "Suspect", "Victim", "Date", "Time", "Place", "Name", "Address",
    "Phone", "Number", "Registration", "Vehicle", "Driver", "Yard", "Road", "Street",
}
_TITLES = r"(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt|Sri|Thiru|Mister)\.?"
_NAME_RE = re.compile(rf"\b(?:{_TITLES}\s+)?([A-Z][a-z]{{2,}}(?:\s+[A-Z][a-z]{{2,}}){{0,2}})\b")
_TAG_RE = re.compile(r"\[[^\]]{1,40}\]:?")           # speaker tags like [Investigator]:


def _words(norm: str) -> List[str]:
    return [w for w in re.findall(r"[a-z]+", norm.lower())]


def object_key(norm: str) -> str:
    """
    Canonical comparison key for an object description.
      "knife-shaped metallic object" -> "knife"
      "White sedan"                  -> "white car"
      "black backpack"               -> "backpack"      (items match on class alone)
    """
    words = [w for w in _words(norm.replace("-shaped", ""))
             if w not in {"metallic", "object", "shaped", "a", "an", "the"}]
    if not words:
        return norm.lower().strip()
    for w in reversed(words):
        if w in ITEMS:
            return ITEMS[w]
    for i in range(len(words) - 1, -1, -1):
        if words[i] in VEHICLES:
            colour = next((c for c in words[:i] if c in COLOURS), None)
            cls = VEHICLES[words[i]]
            return f"{colour} {cls}" if colour else cls
    return " ".join(words)


def _clean(text: str) -> str:
    return _TAG_RE.sub(" ", text)


def extract_terms(text: str) -> List[TextClue]:
    """NAME and OBJECT clues from free text (deduplicated by kind + normalised value)."""
    if not text or not text.strip():
        return []
    text = _clean(text)
    found: Dict[tuple, TextClue] = {}

    # ── objects: [colour] [filler] vehicle  |  item word ─────────────────────
    tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z]+", text)]
    low = [t[0].lower() for t in tokens]
    for i, w in enumerate(low):
        if w in VEHICLES:
            colour = next((low[j] for j in range(max(0, i - 3), i) if low[j] in COLOURS), None)
            if colour:   # a bare "car" matches every car in every video: require a colour
                s, e = tokens[max(0, i - 3):i + 1][0][1], tokens[i][2]
                value = f"{colour} {w}"
                norm = object_key(value)
                found.setdefault(("OBJECT", norm), TextClue("OBJECT", value, norm, "object_phrase", s, e,
                                                            _context(text, s, e)))
        elif w in ITEMS:
            colour = low[i - 1] if i > 0 and low[i - 1] in COLOURS else None
            value = f"{colour} {w}" if colour else w
            norm = ITEMS[w]
            s = tokens[i - 1][1] if colour else tokens[i][1]
            found.setdefault(("OBJECT", norm), TextClue("OBJECT", value, norm, "item_word", s, tokens[i][2],
                                                        _context(text, s, tokens[i][2])))

    # ── names: capitalised sequences not explained by stop words ─────────────
    for m in _NAME_RE.finditer(text):
        raw = m.group(1)
        words = raw.split()
        while words and words[0] in _STOP_CAPS:
            words = words[1:]
        while words and words[-1] in _STOP_CAPS:
            words = words[:-1]
        if not words:
            continue
        name = " ".join(words)
        at_sentence_start = not re.search(r"[A-Za-z0-9,;:]\s*$", text[:m.start()].rstrip()[-3:] or " ") \
            or re.search(r"[.!?]\s*$", text[:m.start()]) is not None or m.start() == 0
        if len(words) == 1 and (at_sentence_start or words[0] in _STOP_CAPS):
            continue                       # a lone capitalised word opening a sentence is just a word
        norm = " ".join(w.lower() for w in words)
        if len(norm) < 4:
            continue
        s, e = m.span(1)
        found.setdefault(("NAME", norm), TextClue("NAME", name, norm, "proper_noun", s, e, _context(text, s, e)))

    return sorted(found.values(), key=lambda c: c.start)


# ── keywords, dates and numbers ───────────────────────────────────────────────
# Everything meaningful in a transcript or document becomes a clue, so that
# anything said in one place and written / seen in another can be matched —
# not only plates, phones and names.

import calendar
from dataclasses import dataclass

try:  # word-frequency table (bundled offline) used to ignore filler words
    from wordfreq import zipf_frequency as _zipf
except Exception:  # pragma: no cover - degrade to the built-in stop list
    _zipf = None

# Words more common than this (Zipf scale; "the" = 7.7, "bank" = 5.2) are filler.
MAX_ZIPF = 5.8
MIN_WORD_LEN = 4

_FILLER = {
    "that", "this", "with", "have", "from", "they", "were", "been", "being", "will", "would", "could",
    "should", "there", "their", "them", "then", "than", "what", "when", "where", "which", "while", "about",
    "after", "before", "again", "also", "very", "just", "only", "some", "such", "into", "over", "under",
    "your", "yours", "mine", "ours", "said", "says", "told", "tell", "going", "gone", "went", "come", "came",
    "back", "here", "like", "make", "made", "know", "knew", "think", "thought", "want", "wanted", "need",
    "take", "took", "give", "gave", "look", "looked", "saw", "seen", "see", "does", "done", "did", "doing",
    "okay", "yeah", "well", "right", "sure", "please", "thank", "thanks", "sorry", "hello", "people",
    "something", "anything", "everything", "nothing", "because", "maybe", "still", "even", "much", "many",
    "more", "most", "other", "another", "same", "each", "every", "both", "never", "always", "around",
}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*[A-Za-z]")
# not part of a longer number/date/decimal ("12.50", "11-10-2026"), but a trailing full stop is fine
_NUM_RE = re.compile(r"(?<!\d)(?<![./-]\d)\d{5,9}(?!\d)(?![./-]\d)")
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MON = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_RES = [
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),                                    # 2026-10-11
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b"),                      # 11/10/2026 (d/m/y)
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\.?,?\s+(\d{{4}})\b", re.I),  # 11 October 2026
    re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),  # October 11, 2026
]


@dataclass(frozen=True)
class WeightedClue(TextClue):
    """A clue carrying a 0-1 distinctiveness weight (rare words weigh more)."""
    weight: float = 1.0


def _stem(word: str) -> str:
    """Tiny, predictable normaliser so 'vans'/'van's'/'Vans' compare equal."""
    w = word.lower().strip("'’-")
    w = re.sub(r"['’]s$", "", w)
    if len(w) > 5 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and re.search(r"(ches|shes|sses|xes|zes)$", w):
        return w[:-2]
    if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _distinctiveness(word: str) -> Optional[float]:
    """None = filler (ignore); otherwise 0.15-1.0, higher for rarer words."""
    if word in _FILLER:
        return None
    if _zipf is None:
        return 0.5
    z = _zipf(word, "en")
    if z >= MAX_ZIPF:
        return None
    return max(0.15, min(1.0, (6.2 - z) / 4.7))      # unknown/rare (z~0) -> 1.0


def _iso(y: int, m: int, d: int) -> Optional[str]:
    if y < 100:
        y += 2000
    try:
        import datetime
        return datetime.date(y, m, d).isoformat()
    except ValueError:
        return None


def extract_dates(text: str) -> List[TextClue]:
    found: Dict[str, TextClue] = {}
    for i, rx in enumerate(_DATE_RES):
        for m in rx.finditer(text):
            g = m.groups()
            if i == 0:
                iso = _iso(int(g[0]), int(g[1]), int(g[2]))
            elif i == 1:
                d, mo = int(g[0]), int(g[1])
                if mo > 12 and d <= 12:               # tolerate m/d/y
                    d, mo = mo, d
                iso = _iso(int(g[2]), mo, d)
            elif i == 2:
                iso = _iso(int(g[2]), _MONTHS[g[1].lower().rstrip(".")], int(g[0]))
            else:
                iso = _iso(int(g[2]), _MONTHS[g[0].lower().rstrip(".")], int(g[1]))
            if iso and iso not in found:
                s, e = m.span()
                found[iso] = TextClue("DATE", m.group(0), iso, f"date_{i}", s, e, _context(text, s, e))
    return list(found.values())


def extract_all_terms(text: str) -> List[TextClue]:
    """NAME + OBJECT + DATE + NUMBER + KEYWORD clues from free text."""
    if not text or not text.strip():
        return []
    cleaned = _clean(text)
    clues: List[TextClue] = list(extract_terms(text))
    clues += extract_dates(cleaned)

    taken_words = set()
    for c in clues:
        taken_words.update(w.lower() for w in re.findall(r"[A-Za-z]+", c.value))
        if c.kind == "OBJECT":                      # "white van" -> don't also emit "van"/"white"
            taken_words.update(_words(c.norm))

    # long digit strings that are not phones / dates (invoice, account, reference numbers)
    date_spans = [(c.start, c.end) for c in clues if c.kind == "DATE"]
    for m in _NUM_RE.finditer(cleaned):
        s, e = m.span()
        if any(s < de and e > ds for ds, de in date_spans):
            continue
        clues.append(TextClue("NUMBER", m.group(0), m.group(0), "digits", s, e, _context(cleaned, s, e)))

    seen = set()
    for m in _WORD_RE.finditer(cleaned):
        raw = m.group(0)
        low = raw.lower()
        if len(low) < MIN_WORD_LEN or low in taken_words:
            continue
        w = _distinctiveness(low)
        if w is None:
            continue
        norm = _stem(low)
        if norm in seen or norm in taken_words:
            continue
        seen.add(norm)
        s, e = m.span()
        clues.append(WeightedClue("KEYWORD", low, norm, "keyword", s, e, _context(cleaned, s, e), weight=round(w, 2)))
    return clues
