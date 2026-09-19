"""
SunoBolo — turning a spoken sentence into stock movements.

THE WHOLE IDEA IN FOUR LINES:
A shop has ~50 items, ~10 units, 2 directions. That is a tiny answer space.
So we never try to "understand" the sentence. We scan it for four known things
 - quantity, unit, direction, item - and look each one up in a list we wrote.
The item lookup is fuzzy, which is what makes it work on messy speech.

    "bhaiya do kilo chawal dena"
              |   |     |     |
              |   |     |     +-- direction -> OUT
              |   |     +-------- item      -> fuzzy match -> Rice (94%)
              |   +-------------- unit      -> kg
              +------------------ quantity  -> 2

No machine learning. No training. Just lists and one fuzzy string match.
"""

import re
from rapidfuzz import fuzz

# ── Confidence thresholds ────────────────────────────────────────────────────
ACCEPT = 85   # sure enough to pre-tick for bulk approval
SUGGEST = 60  # unsure - show "did you mean" choices instead
# Below SUGGEST we throw the result away. In Counter Mode the app is listening
# to a whole shop, so most of what it hears is not a transaction at all.

# ── Number words ─────────────────────────────────────────────────────────────
# Hindi + Telugu. "dhai/derh/sawa" are the half-quantities shopkeepers actually say.
NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "pandrah": 15, "bees": 20, "pachchis": 25,
    "tees": 30, "chalis": 40, "pachas": 50, "saath": 60, "sattar": 70,
    "assi": 80, "nabbe": 90,
    "okati": 1, "rendu": 2, "moodu": 3, "naalugu": 4, "aidu": 5, "aaru": 6,
    "edu": 7, "enimidi": 8, "tommidi": 9, "padi": 10, "iravai": 20, "yabhai": 50,
    "dhai": 2.5, "derh": 1.5, "sawa": 1.25, "paune": 0.75, "adha": 0.5, "aadha": 0.5,
    "sau": 100, "hazaar": 1000, "nooru": 100, "veyyi": 1000,   # multipliers
}
MULTIPLIERS = {"sau", "hazaar", "nooru", "veyyi"}

# ── Units that mean the same everywhere ──────────────────────────────────────
# unit spoken -> (base unit it converts to, how many base units it is worth)
UNITS = {
    "kg": ("kg", 1), "kilo": ("kg", 1), "kilos": ("kg", 1), "kilogram": ("kg", 1),
    "किलो": ("kg", 1), "కిలో": ("kg", 1),
    "gram": ("kg", 0.001), "grams": ("kg", 0.001), "ग्राम": ("kg", 0.001),
    "quintal": ("kg", 100), "क्विंटल": ("kg", 100),
    "pc": ("pc", 1), "piece": ("pc", 1), "pieces": ("pc", 1), "nag": ("pc", 1),
    "packet": ("pc", 1), "packets": ("pc", 1), "पैकेट": ("pc", 1),
    "dozen": ("pc", 12), "darjan": ("pc", 12), "दर्जन": ("pc", 12), "డజను": ("pc", 12),
    "tray": ("pc", 30), "ट्रे": ("pc", 30),
    "litre": ("litre", 1), "liter": ("litre", 1), "lt": ("litre", 1),
    "लीटर": ("litre", 1), "లీటరు": ("litre", 1),
    "ml": ("litre", 0.001),
}
# Units like "bori" and "carton" are NOT here on purpose: 1 bori of rice is 50 kg
# but 1 bori of sugar is 25 kg. Those live per-item, in item["packs"].

# ── Action words ─────────────────────────────────────────────────────────────
IN_WORDS = {"aaya", "aayi", "aaye", "aya", "liya", "kharida", "khareeda",
            "mangwaya", "mila", "आया", "लिया",
            "vacchindi", "vachindi", "konnanu", "techanu", "వచ్చింది",
            "came", "bought", "received", "add", "added", "in"}

# NOTE: "do" is deliberately NOT here. In a shop it almost always means the
# number 2 ("do kilo"), not "de do" / give. Leaving it in made every
# "do kilo chawal aaya" register as a sale.
OUT_WORDS = {"dena", "de", "diya", "becha", "bech", "gaya", "gayi",
            "nikala", "chahiye", "देना", "बेचा", "गया",
            "kavali", "ammanu", "ammesanu", "ichanu", "poyindi", "కావాలి", "అమ్మాను",
            "sold", "sell", "give", "need", "out", "remove"}

QUERY_WORDS = {"kitna", "kitne", "kitni", "bacha", "bache", "batao", "कितना", "कितने",
               "enta", "entha", "unnayi", "undi", "cheppu", "ఎంత",
               "how", "much", "many", "check"}

LOW_WORDS = {"khatam", "kam", "mangwana", "order", "खत्म", "कम",
             "takkuva", "avvali", "తక్కువ",
             "low", "running", "finished", "reorder"}

# Sentences can carry more than one item: "do kilo chawal AUR ek maggi".
SPLITTERS = re.compile(r"\s+(?:aur|और|and|mariyu|మరియు|plus)\s+")

# Common filler heard at a counter. Without this, "aaj" scores 57 against "anda"
# - close enough to the cut-off to be worth naming explicitly.
STOPWORDS = {"aaj", "bhai", "bhaiya", "kya", "hai", "hain", "nahi", "haan",
             "accha", "theek", "arre", "are", "suno", "dekho", "abhi", "bas",
             "please", "the", "yes", "okay", "ok", "andi", "sir", "madam"}


def normalise(text):
    """Lowercase and strip punctuation. Hindi/Telugu script passes through
    untouched - the fuzzy matcher does not care which alphabet it is looking at."""
    text = text.lower().strip()
    return re.sub(r"[^\w\sऀ-ॿఀ-౿.]", " ", text)


def to_number(tokens):
    """'bees' -> 20 | '20' -> 20 | 'teen sau' -> 300 | 'dhai' -> 2.5 | none -> None"""
    total = None
    for t in tokens:
        if re.fullmatch(r"\d+(?:\.\d+)?", t):
            total = float(t)
        elif t in NUMBERS:
            if t in MULTIPLIERS and total:
                total *= NUMBERS[t]      # "teen sau" = 3 x 100
            else:
                total = NUMBERS[t]
    return total


def find_unit(tokens, item):
    """Return (spoken unit, how many base units it equals).

    Item pack sizes win over the global table, because 'bag' only means
    something once you know which item is in the bag."""
    for t in tokens:
        if t in item["packs"]:
            return t, item["packs"][t]
        if t in UNITS:
            return t, UNITS[t][1]
    return item["base_unit"], 1          # nothing said -> assume the base unit


def find_direction(tokens, default):
    """Did stock come IN or go OUT? Checked on the whole sentence, because the
    verb usually sits at the end: 'do kilo chawal DENA'."""
    if tokens & OUT_WORDS:
        return "out"
    if tokens & IN_WORDS:
        return "in"
    return default


def match_item(text, items, limit=3):
    """Score every item, best first.

    THIS IS THE IMPORTANT BIT. One fuzzy comparison solves two problems at once:
      - speech-to-text errors   'chaawal', 'chowal'  -> Rice
      - different languages     'rice', 'chawal', 'चावल', 'biyyam' -> Rice
    Both are just near-misses against the item's alias list, so we need neither
    a spell-checker nor a translator.

    We compare word-by-word rather than sentence-to-alias, because the extra
    words in a sentence drag the score down: "chowal" scores 83 against
    "chawal", but "paanch kilo chowal aaya" scores only 34.
    """
    words = [w for w in text.split()
             if len(w) >= 3 and w not in NUMBERS and w not in UNITS and w not in STOPWORDS]
    scored = []
    for it in items:
        best = 0
        for alias in it["aliases"]:
            alias = alias.lower()
            if " " in alias:
                # multi-word alias ("toor dal") has to be matched against the phrase
                best = max(best, fuzz.token_set_ratio(text, alias))
            for w in words:
                best = max(best, fuzz.ratio(w, alias))
        scored.append((best, it))
    scored.sort(key=lambda pair: -pair[0])
    return scored[:limit]


def parse(text, items, mode="command"):
    """Turn one sentence into a list of proposed stock movements.

    mode="counter" is passive listening (overheard talk is usually a sale),
    mode="command" is the mic button (a deliberate entry is usually a delivery).
    """
    text = normalise(text)
    if not text:
        return []
    tokens = set(text.split())

    # Questions produce an answer, not a stock change.
    if tokens & LOW_WORDS and not (tokens & IN_WORDS):
        return [{"action": "query_low"}]
    if tokens & QUERY_WORDS:
        top = match_item(text, items)
        if top and top[0][0] >= SUGGEST:
            return [{"action": "query_item", "item": top[0][1], "confidence": top[0][0]}]
        return [{"action": "query_low"}]

    direction = find_direction(tokens, "out" if mode == "counter" else "in")

    moves = []
    for fragment in SPLITTERS.split(text):
        words = fragment.split()
        ranked = match_item(fragment, items)
        if not ranked or ranked[0][0] < SUGGEST:
            continue                      # nothing recognisable - stay silent

        score, item = ranked[0]
        unit, factor = find_unit(words, item)
        qty = to_number(words) or 1
        moves.append({
            "action": "stock_" + direction,
            "item": item,
            "qty": qty,
            "unit": unit,
            "qty_base": round(qty * factor * (-1 if direction == "out" else 1), 3),
            "confidence": score,
            "sure": score >= ACCEPT,
            # Shown as one-tap "did you mean" chips when we are not confident.
            "candidates": [i for _, i in ranked[1:]] if score < ACCEPT else [],
            "transcript": text,
        })
    return moves
