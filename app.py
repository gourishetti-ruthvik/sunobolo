"""
SunoBolo backend.  Run:  uvicorn app:app --reload

Two tables, six endpoints, no ORM.

The one design decision worth remembering: we never store a stock number.
Every change is a new row in `txns`, and current stock is SUM(qty_base).
That gives us history, undo and an audit trail for free, and means a wrong
entry can be corrected instead of having already overwritten the truth.
"""

import json
import os
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

import parse as nlu

DB = os.environ.get("DB_PATH", "sunobolo.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  name_hi       TEXT,
  name_te       TEXT,
  aliases       TEXT NOT NULL,        -- JSON list: every spelling, every language
  base_unit     TEXT NOT NULL,        -- kg | pc | litre
  packs         TEXT NOT NULL,        -- JSON: {"bori": 50} -> 1 bori = 50 kg
  reorder_level REAL DEFAULT 0,
  target_level  REAL DEFAULT 0,
  last_price    REAL
);

CREATE TABLE IF NOT EXISTS txns (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id    INTEGER NOT NULL REFERENCES items(id),
  qty        REAL NOT NULL,           -- 2          (what was said)
  unit       TEXT NOT NULL,           -- 'bori'     (what was said)
  qty_base   REAL NOT NULL,           -- +100 or -100, always in base_unit
  transcript TEXT,                    -- the actual sentence - audit trail
  lang       TEXT,
  confidence REAL,
  source     TEXT,                    -- counter | command | manual | undo
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# name, hi, te, base, packs, reorder, target, price, aliases, opening stock
SEED = [
    ("Rice", "चावल", "బియ్యం", "kg", {"bori": 50, "bag": 25}, 50, 150, 58,
     ["rice", "chawal", "chaawal", "chowal", "चावल", "biyyam", "బియ్యం", "basmati"], 42),
    ("Sugar", "चीनी", "చక్కెర", "kg", {"bag": 25}, 25, 75, 44,
     ["sugar", "cheeni", "chini", "चीनी", "chakkera", "చక్కెర", "shakkar"], 18),
    ("Wheat Flour", "आटा", "గోధుమ పిండి", "kg", {"bag": 10}, 40, 120, 38,
     ["atta", "aata", "आटा", "flour", "godhuma pindi", "గోధుమ పిండి"], 95),
    ("Toor Dal", "तूर दाल", "కంది పప్పు", "kg", {"bag": 30}, 15, 50, 142,
     ["dal", "daal", "toor dal", "tur dal", "arhar", "दाल", "kandi pappu", "కంది పప్పు"], 8),
    ("Sunflower Oil", "तेल", "నూనె", "litre", {"tin": 15, "carton": 12}, 20, 60, 135,
     ["oil", "tel", "तेल", "sunflower oil", "nune", "నూనె", "refined"], 31),
    ("Maggi", "मैगी", "మ్యాగీ", "pc", {"carton": 96, "peti": 96}, 48, 192, 12,
     ["maggi", "magi", "मैगी", "మ్యాగీ", "noodles"], 24),
    ("Tea Powder", "चाय पत्ती", "టీ పొడి", "kg", {"box": 1}, 5, 20, 340,
     ["tea", "chai", "chai patti", "चाय", "चाय पत्ती", "టీ పొడి"], 6),
    ("Eggs", "अंडा", "గుడ్లు", "pc", {"tray": 30, "dozen": 12}, 60, 180, 6,
     ["egg", "eggs", "anda", "ande", "अंडा", "gudlu", "గుడ్లు"], 0),
]


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row        # rows behave like dicts
    return con


def setup():
    con = db()
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM items LIMIT 1").fetchone():
        for n, hi, te, bu, p, r, t, pr, a, opening in SEED:
            cur = con.execute(
                "INSERT INTO items (name,name_hi,name_te,base_unit,packs,reorder_level,"
                "target_level,last_price,aliases) VALUES (?,?,?,?,?,?,?,?,?)",
                (n, hi, te, bu, json.dumps(p), r, t, pr, json.dumps(a)))
            # Opening stock is itself a ledger row - there is no other way to
            # have stock, which is what keeps every number traceable.
            if opening:
                con.execute(
                    "INSERT INTO txns (item_id,qty,unit,qty_base,transcript,source)"
                    " VALUES (?,?,?,?,'opening stock','seed')",
                    (cur.lastrowid, opening, bu, opening))
    con.commit()
    con.close()


app = FastAPI(title="SunoBolo")
setup()


def stock_rows():
    """Every item with its current stock. This is the only place stock is computed."""
    con = db()
    rows = con.execute("""
        SELECT i.*, COALESCE(SUM(t.qty_base), 0) AS stock
        FROM items i LEFT JOIN txns t ON t.item_id = i.id
        GROUP BY i.id ORDER BY i.name
    """).fetchall()
    con.close()
    out = []
    for r in rows:
        d = dict(r)
        d["aliases"] = json.loads(d["aliases"])
        d["packs"] = json.loads(d["packs"])
        d["stock"] = round(d["stock"], 2)
        d["status"] = ("out" if d["stock"] <= 0
                       else "low" if d["stock"] <= d["reorder_level"] else "ok")
        # Negative stock is allowed on purpose - the shelf and the book really do
        # drift apart in a shop. But it must be SHOWN as a mismatch, not left
        # looking like a broken number.
        d["mismatch"] = d["stock"] < 0
        out.append(d)
    return out


@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/stock")
def stock():
    return stock_rows()


@app.post("/parse")
def do_parse(body: dict):
    """Read-only on purpose. Nothing here touches the database - the user has
    to approve a movement before it becomes real."""
    moves = nlu.parse(body.get("text", ""), stock_rows(), body.get("mode", "command"))
    for m in moves:                       # trim the item down for the wire
        if "item" in m:
            m["item"] = {k: m["item"][k] for k in
                         ("id", "name", "name_hi", "name_te", "base_unit", "packs", "stock")}
        m["candidates"] = [{"id": c["id"], "name": c["name"],
                            "name_hi": c["name_hi"], "name_te": c["name_te"]}
                           for c in m.get("candidates", [])]
    return {"moves": moves, "lang": body.get("lang", "hi")}


@app.post("/commit")
def commit(body: dict):
    """The only endpoint that writes. One approved movement -> one ledger row."""
    item = next((i for i in stock_rows() if i["id"] == body.get("item_id")), None)
    if not item:
        raise HTTPException(404, "unknown item")
    try:
        qty = float(body["qty"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "qty must be a number")

    unit = body.get("unit") or item["base_unit"]
    # per-item pack size wins over the global table, same rule as the parser
    factor = item["packs"].get(unit) or nlu.UNITS.get(unit, (None, 1))[1]
    qty_base = qty * factor * (-1 if body.get("direction") == "out" else 1)

    con = db()
    cur = con.execute(
        "INSERT INTO txns (item_id,qty,unit,qty_base,transcript,lang,confidence,source)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (item["id"], qty, unit, qty_base, body.get("transcript"), body.get("lang"),
         body.get("confidence"), body.get("source", "command")))
    con.commit()
    txn_id = cur.lastrowid
    con.close()
    return {"txn_id": txn_id, "item": item["name"],
            "applied": qty_base, "new_total": round(item["stock"] + qty_base, 2),
            "base_unit": item["base_unit"]}


@app.post("/undo/{txn_id}")
def undo(txn_id: int):
    """Reverse a movement by adding the opposite row. We never delete history."""
    con = db()
    t = con.execute("SELECT * FROM txns WHERE id=?", (txn_id,)).fetchone()
    if not t:
        con.close()
        raise HTTPException(404, "unknown entry")
    con.execute(
        "INSERT INTO txns (item_id,qty,unit,qty_base,transcript,lang,source)"
        " VALUES (?,?,?,?,?,?,'undo')",
        (t["item_id"], t["qty"], t["unit"], -t["qty_base"], f"undo of #{txn_id}", t["lang"]))
    con.commit()
    con.close()
    return {"ok": True}


@app.get("/search")
def search(q: str = ""):
    """Find an item by ANY alias in ANY language: 'rice', 'chawal' and 'बियाम'
    all reach the same row. This is the escape hatch when a match is wrong."""
    q = q.strip().lower()
    rows = stock_rows()
    if not q:
        return rows
    return [i for i in rows
            if q in i["name"].lower() or any(q in a.lower() for a in i["aliases"])]


@app.post("/items")
def add_item(body: dict):
    """Add something the shop stocks that we had never heard of.

    The word actually spoken becomes the item's first alias, so the very next
    time it is said it matches - no model, no retraining, just a row."""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    base = body.get("base_unit") or "pc"
    if base not in ("kg", "pc", "litre"):
        raise HTTPException(400, "base_unit must be kg, pc or litre")
    heard = (body.get("heard") or "").strip().lower()
    aliases = sorted({name.lower()} | ({heard} if heard else set()))

    con = db()
    cur = con.execute(
        "INSERT INTO items (name,name_hi,name_te,aliases,base_unit,packs,"
        "reorder_level,target_level,last_price) VALUES (?,?,?,?,?,'{}',?,?,0)",
        (name, name, name, json.dumps(aliases), base,
         float(body.get("reorder_level") or 0), float(body.get("target_level") or 0)))
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return {"id": new_id, "name": name, "base_unit": base}


@app.post("/items/{item_id}/alias")
def learn_alias(item_id: int, body: dict):
    """THE LEARNING STEP. Every correction teaches the lexicon.

    When the owner says "tamatar" and fixes the match to Tomato, that word is
    stored as an alias of Tomato. Correct it once; it is right from then on.
    This is why the system gets better with use without any training."""
    word = (body.get("word") or "").strip().lower()
    if not word:
        return {"learned": False}
    con = db()
    row = con.execute("SELECT aliases FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "unknown item")
    aliases = json.loads(row["aliases"])
    if word in (a.lower() for a in aliases):
        con.close()
        return {"learned": False}          # already knew it
    aliases.append(word)
    con.execute("UPDATE items SET aliases=? WHERE id=?", (json.dumps(aliases), item_id))
    con.commit()
    con.close()
    return {"learned": True, "word": word}


@app.get("/alerts")
def alerts():
    """Low stock, with how much to order expressed in the unit you actually buy in."""
    out = []
    for i in stock_rows():
        if i["status"] == "ok":
            continue
        need = i["target_level"] - i["stock"]
        unit, factor = next(iter(i["packs"].items()), (i["base_unit"], 1))
        out.append({**i, "need": round(need, 1),
                    "order_qty": max(1, round(need / factor)), "order_unit": unit})
    return out


@app.get("/item/{item_id}")
def item(item_id: int):
    i = next((x for x in stock_rows() if x["id"] == item_id), None)
    if not i:
        raise HTTPException(404, "unknown item")
    con = db()
    i["history"] = [dict(r) for r in con.execute(
        "SELECT * FROM txns WHERE item_id=? ORDER BY id DESC LIMIT 15", (item_id,))]
    con.close()
    return i


@app.get("/export.csv", response_class=PlainTextResponse)
def export():
    """Backup. The owner's data should never be locked inside our database."""
    con = db()
    rows = con.execute(
        "SELECT t.id,t.created_at,i.name,t.qty,t.unit,t.qty_base,t.source,t.transcript"
        " FROM txns t JOIN items i ON i.id=t.item_id ORDER BY t.id").fetchall()
    con.close()
    lines = ["id,when,item,qty,unit,change,source,heard"]
    lines += [",".join(f'"{v}"' for v in r) for r in rows]
    return "\n".join(lines)
