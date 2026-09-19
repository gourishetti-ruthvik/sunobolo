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
    ("4kg chawal aaya",              "command", "Rice", +4),      # "4kg" glued together
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

    # Overheard chatter must be dropped, not guessed at. Counter Mode uses a
    # higher floor than the mic button for exactly this reason.
    assert parse("aaj garmi bahut hai", ITEMS, "counter") == []
    assert parse("namaste bhaiya kaise ho", ITEMS, "counter") == []
    assert parse("aaj bahut garmi hai", ITEMS, "counter") == []

    # An item the shop does not stock must NOT be forced onto the nearest name.
    # "tamatar" scored 72.7 against "aata" - high enough to look like a match.
    u = parse("char kilo tamatar dena", ITEMS, "command")
    assert u and u[0]["action"] == "unknown_item", u
    assert u[0]["heard"] == "tamatar" and u[0]["qty"] == 4, u
    # ...and in Counter Mode it is dropped silently instead, since nobody asked.
    assert parse("char kilo tamatar dena", ITEMS, "counter") == []

    # "sab nikal do" - a clear instruction with no item named. Must ask WHICH
    # item, not claim we do not recognise the word. ("do" here is the imperative
    # helper, not the number 2; "sab" is a quantity, not an item name.)
    n = parse("sab nikal do", ITEMS, "command")
    assert n and n[0]["action"] == "need_item", n
    assert n[0]["direction"] == "out" and n[0]["all"] is True, n

    # ...and with an item named, "all" means the whole shelf.
    ITEMS[0]["stock"] = 40
    a = parse("sab chawal nikal do", ITEMS, "command")
    assert a[0]["qty"] == 40 and a[0]["qty_base"] == -40, a

    print(f"all {len(CASES) + 14} checks passed")


if __name__ == "__main__":
    run()
