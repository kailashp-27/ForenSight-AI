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
    "usb": "usb drive", "pendrive": "usb drive", "thumbdrive": "usb drive", "flashdrive": "usb drive",
    "harddrive": "hard drive", "ssd": "hard drive",
}
# "drive" alone is also a verb ("I'll drive there"): it is only an item after one of these.
_DRIVE_PRE = {"usb", "flash", "thumb", "pen", "hard", "external", "memory", "encrypted", "small", "metallic",
              "portable", "data", "storage", "the", "a", "that", "this", "my", "your"}
_GENERIC_ITEMS = {"stick", "box", "bag", "bottle", "bat"}   # lose to a more specific item word

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
    "Tier", "Level", "Floor", "Room", "Sector", "Unit", "Zone", "Block", "Gate", "Section", "Visitor",
}
# Common given names / surnames (Indian + Western). A phrase is only a NAME when it contains one of
# these, carries a title / initials, follows a naming cue, or is made only of rare words and no
# place/organisation vocabulary. This is what stops "Cooling Units" or "Apex Dynamics" being people.
_KNOWN_NAMES = set("""
ramesh suresh mahesh rajesh dinesh ganesh naresh mukesh hitesh kumar babu priya anita sunita kavita meena
pooja neha sneha divya lakshmi radha sita gita rahul arjun deepak vijay ajay sanjay anil amit rohit ravi
krishna vikram manoj prakash mohan sundar senthil murugan karthik selvam raja rani asha usha latha
singh sharma patel khan reddy iyer nair gupta verma joshi mehta shah das roy ghosh bose pillai menon rao
john mark paul james david michael robert william richard thomas charles daniel matthew andrew peter steven
brian kevin george edward jason jack tom sam ben alex chris joe henry oliver harry noah liam ethan
mary anna maria sarah emma olivia sophia emily jessica jennifer linda susan karen lisa nancy laura mia
smith jones brown taylor wilson davis miller anderson moore clark lewis walker allen young king wright
scott baker adams nelson carter mitchell turner phillips campbell parker evans edwards collins stewart
morris murphy cook rogers morgan cooper peterson reed bailey bell kelly howard ward cox richardson wood
watson brooks bennett hughes price sanders ross foster powell jenkins perry russell sullivan fisher
henderson cole vance stone hunt grant mason hayes
""".split())
_NOT_NAME_WORDS = set("""
dynamics systems services solutions technologies industries enterprises group company corporation limited
ltd inc llc department dept police station units unit log location sign visitor dock cooling loading trash
scrap server rack security guard maintenance window sector floor entrance exit hall office building warehouse
bank hospital school college university city town road street avenue park bridge north south east west
apex page torn emergency repair reason sign-in logbook register report statement summary section incident
investigation evidence exhibit camera footage cctv shift duty access control panel room tier level zone
gate bay lot platform terminal tower aisle hangar pier wing block basement rooftop lobby parking garage
""".split())
_NAME_CUES = re.compile(
    r"(?:\bname\b|\bmr\b|\bmrs\b|\bms\b|\bmiss\b|\bdr\b|\bshri\b|\bsmt\b|\bnamed\b|\bcalled\b|\bsigned\b|"
    r"\bsuspect\b|\bvictim\b|\bwitness\b|\bdriver\b|\bofficer\b|\bowner\b|\bcontact\b|\bguard\b|"
    r"\bvisitor\b|\bemployee\b|\bmanager\b|\bresident\b|\bby\b)\W{0,3}$", re.I)
_TITLES = r"(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt|Sri|Thiru|Mister)\.?"
_NAME_RE = re.compile(rf"\b(?:{_TITLES}\s+)?([A-Z][a-z]{{2,}}(?:\s+[A-Z][a-z]{{2,}}){{0,3}})\b")
_TAG_RE = re.compile(r"\[[^\]]{1,40}\]:?")           # speaker tags like [Investigator]:


def _name_ok(words: List[str], text: str, start: int, titled: bool) -> bool:
    """Does this capitalised phrase plausibly name a person?"""
    low = [w.lower() for w in words]
    if any(w in _NOT_NAME_WORDS for w in low):
        return False
    if titled or any(w in _KNOWN_NAMES for w in low):
        return True
    if _NAME_CUES.search(text[max(0, start - 28):start]):
        return True
    if _zipf is None:
        return len(words) >= 2
    # otherwise only phrases made of RARE words (real surnames are rare words)
    return all(_zipf(w, "en") < 3.8 for w in low)


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
    found = [ITEMS[w] for w in words if w in ITEMS]
    for i, w in enumerate(words):
        if w == "drive" and i > 0 and (words[i - 1] in _DRIVE_PRE or words[i - 1] in COLOURS):
            found.append("usb drive")
    if found:
        specific = [f for f in found if f not in _GENERIC_ITEMS]
        return (specific or found)[0]
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
        elif w == "drive" and i > 0 and (low[i - 1] in _DRIVE_PRE or low[i - 1] in COLOURS):
            colour = low[i - 1] if low[i - 1] in COLOURS else None
            value = f"{colour} drive" if colour else f"{low[i - 1]} drive"
            s = tokens[i - 1][1]
            found.setdefault(("OBJECT", "usb drive"), TextClue("OBJECT", value, "usb drive", "item_word", s,
                                                               tokens[i][2], _context(text, s, tokens[i][2])))
        elif w in ITEMS:
            colour = low[i - 1] if i > 0 and low[i - 1] in COLOURS else None
            value = f"{colour} {w}" if colour else w
            norm = ITEMS[w]
            s = tokens[i - 1][1] if colour else tokens[i][1]
            found.setdefault(("OBJECT", norm), TextClue("OBJECT", value, norm, "item_word", s, tokens[i][2],
                                                        _context(text, s, tokens[i][2])))

    # ── names written as initials + surname: "J. Vance", "J.VANCE" ──────────
    for m in re.finditer(r"(?<![\w-])((?:[A-Z]\.\s?){1,2})([A-Z][A-Za-z]{2,})\b", text):
        initials = re.sub(r"[^A-Za-z]", "", m.group(1)).lower()
        surname = m.group(2).lower()
        if surname in _NOT_NAME_WORDS:          # "...-V. Visitor pass" is not a person
            continue
        norm = f"{initials} {surname}"
        s, e = m.span()
        found.setdefault(("NAME", norm), TextClue("NAME", m.group(0), norm, "initials_surname", s, e,
                                                  _context(text, s, e)))

    # ── names: capitalised sequences not explained by stop words ─────────────
    for m in _NAME_RE.finditer(text):
        raw = m.group(1)
        words = raw.split()
        n_before = len(words)
        while words and (words[0] in _STOP_CAPS or words[0].lower() in _NOT_NAME_WORDS):
            words = words[1:]
        trimmed_front = len(words) != n_before
        while words and (words[-1] in _STOP_CAPS or words[-1].lower() in _NOT_NAME_WORDS):
            words = words[:-1]
        if not words:
            continue
        name = " ".join(words)
        titled = bool(re.match(rf"{_TITLES}\s", text[m.start():m.start(1) + 1]))
        if not _name_ok(words, text, m.start(1), titled):
            continue
        at_sentence_start = not re.search(r"[A-Za-z0-9,;:]\s*$", text[:m.start()].rstrip()[-3:] or " ") \
            or re.search(r"[.!?]\s*$", text[:m.start()]) is not None or m.start() == 0
        if len(words) == 1 and ((at_sentence_start and not trimmed_front) or words[0] in _STOP_CAPS):
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


# ── clock times and places ────────────────────────────────────────────────────
_TIME_RES = [
    re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]\.?m\.?)?(?![\d])", re.I),   # 1:00 AM, 01:34:12
    re.compile(r"(?<![\d:.])(\d{1,2})\s*([ap]\.?m\.?)(?![a-z])", re.I),                         # 1 AM
    re.compile(r"(?<![\d])([01]\d|2[0-3])([0-5]\d)\s*(?:hrs|hours|h)\b", re.I),                  # 0134 hrs
]
_LOC_WORD = (r"sector|zone|bay|block|building|bldg|room|floor|level|gate|dock|wing|unit|lot|platform|"
             r"terminal|tower|rack|aisle|bunker|hangar|pier")
_LOC_RES = [
    # "Sector 4", "Bay B2", "Gate 7", "Rack #04", "North Dock", "South dock"
    re.compile(rf"\b(?:(north|south|east|west|upper|lower|main)\s+)?({_LOC_WORD})\b(?:\s*[#-]?\s*([A-Za-z]?\d{{1,3}}[A-Za-z]?))?", re.I),
    re.compile(r"\b(server\s*room|loading\s*dock|stairwell|basement|rooftop|lobby|warehouse|car\s*park|"
               r"parking\s*(?:lot|garage)|loading\s*bay|control\s*room|data\s*cent(?:er|re))\b", re.I),
]
_QUALIFIED_ALONE = {"dock", "gate", "wing"}      # "the dock" is a place even without a number


def extract_times(text: str) -> List[TextClue]:
    found: Dict[str, TextClue] = {}
    for i, rx in enumerate(_TIME_RES):
        for m in rx.finditer(text):
            g = m.groups()
            try:
                if i == 0:
                    h, mi, ap = int(g[0]), int(g[1]), (g[3] or "")
                elif i == 1:
                    h, mi, ap = int(g[0]), 0, g[1]
                else:
                    h, mi, ap = int(g[0]), int(g[1]), ""
            except ValueError:
                continue
            ap = ap.lower().replace(".", "")
            if ap == "pm" and h < 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
            if h > 23 or mi > 59:
                continue
            if i == 0 and not ap and not g[2] and h > 12 and False:
                continue
            norm = f"{h:02d}:{mi:02d}"
            if norm not in found:
                s, e = m.span()
                found[norm] = TextClue("TIME", m.group(0).strip(), norm, f"time_{i}", s, e, _context(text, s, e))
    return list(found.values())


def extract_locations(text: str) -> List[TextClue]:
    found: Dict[str, TextClue] = {}
    for m in _LOC_RES[0].finditer(text):
        compass, word, num = m.group(1), m.group(2).lower(), m.group(3)
        if not num and not compass and word not in _QUALIFIED_ALONE:
            continue                    # "the floor", "a unit": too generic without a qualifier
        norm = " ".join(x for x in [(compass or "").lower(), word, (num or "").lstrip("0").lower() or ("0" if num else "")] if x)
        s, e = m.span()
        found.setdefault(norm, TextClue("LOCATION", m.group(0).strip(), norm, "place", s, e, _context(text, s, e)))
    for m in _LOC_RES[1].finditer(text):
        norm = re.sub(r"\s+", " ", m.group(1).lower())
        s, e = m.span()
        found.setdefault(norm, TextClue("LOCATION", m.group(0).strip(), norm, "place", s, e, _context(text, s, e)))
    return list(found.values())


def extract_all_terms(text: str) -> List[TextClue]:
    """NAME + OBJECT + DATE + NUMBER + KEYWORD clues from free text."""
    if not text or not text.strip():
        return []
    cleaned = _clean(text)
    clues: List[TextClue] = list(extract_terms(text))
    clues += extract_dates(cleaned)
    clues += extract_times(cleaned)
    clues += extract_locations(cleaned)

    taken_words = set()
    for c in clues:
        taken_words.update(w.lower() for w in re.findall(r"[A-Za-z]+", c.value))
        if c.kind in ("OBJECT", "LOCATION"):        # "white van" / "sector 4": no extra "van"/"sector"
            taken_words.update(_words(c.norm))

    # long digit strings that are not phones / dates (invoice, account, reference numbers)
    date_spans = [(c.start, c.end) for c in clues if c.kind in ("DATE", "TIME")]
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
