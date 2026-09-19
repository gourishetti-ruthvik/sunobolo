"""Run with:  python test_parse.py

This table IS the specification of what speech we support. When the demo
mishears something, add the sentence here first, then fix parse.py.
"""
from parse import parse

ITEMS = [
    {"id": 1, "name": "Rice", "base_unit": "kg", "packs": {"bori": 50, "bag": 25},
     "aliases": ["rice", "chawal", "chaawal", "चावल", "biyyam", "బియ్యం"]},
    {"id": 2, "name": "Maggi", "base_unit": "pc", "packs": {"carton": 96, "peti": 96},
     "aliases": ["maggi", "मैगी", "noodles"]},
    {"id": 3, "name": "Eggs", "base_unit": "pc", "packs": {"tray": 30},
     "aliases": ["egg", "anda", "ande", "अंडा", "gudlu"]},
]

# sentence, mode, expected item name, expected change in base units
CASES = [
    ("bees kilo chawal aaya",        "command", "Rice", +20),     # Hindi, IN
    ("do bori chawal aaya",          "command", "Rice", +100),    # per-item pack size
    ("teen sau kilo chawal aaya",    "command", "Rice", +300),    # "teen sau" = 300
    ("dhai kilo chawal becha",       "command", "Rice", -2.5),    # half quantity
    ("50 kg chawal aaya",            "command", "Rice", +50),     # digits
    ("rendu bori biyyam vacchindi",  "command", "Rice", +100),    # Telugu
    ("2 tray anda becha",            "command", "Eggs", -60),     # tray = 30 pc
    ("ek carton maggi aaya",         "command", "Maggi", +96),    # carton = 96 pc
    ("das kilo chaawal aaya",        "command", "Rice", +10),     # misspelt by the recogniser
    ("paanch kilo chowal aaya",      "command", "Rice", +5),      # misspelt differently
    ("bhaiya do kilo chawal dena",   "counter", "Rice", -2),      # overheard sale
    ("paanch anda chahiye",          "counter", "Eggs", -5),      # customer asking
]


def run():
    for text, mode, item, change in CASES:
        got = parse(text, ITEMS, mode)
        assert got, f"nothing parsed from: {text}"
        m = got[0]
        assert m["item"]["name"] == item, f"{text!r} -> {m['item']['name']}, wanted {item}"
        assert m["qty_base"] == change, f"{text!r} -> {m['qty_base']}, wanted {change}"

    # One sentence, two items.
    two = parse("do kilo chawal aur ek maggi dena", ITEMS, "counter")
    assert len(two) == 2, f"expected 2 movements, got {len(two)}"
    assert {m["item"]["name"] for m in two} == {"Rice", "Maggi"}

    # Questions must never become stock changes.
    assert parse("chawal kitna hai", ITEMS)[0]["action"] == "query_item"
    assert parse("kya khatam ho raha hai", ITEMS)[0]["action"] == "query_low"

    # Overheard chatter with no item in it must be dropped, not guessed at.
    assert parse("aaj garmi bahut hai", ITEMS, "counter") == []

    print(f"all {len(CASES) + 4} checks passed")


if __name__ == "__main__":
    run()
