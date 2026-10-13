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
from typing import Dict, List

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
