"""
SunoBolo backend.  Run:  uvicorn app:app --reload

Three tables, no ORM.

Two design decisions worth remembering:

1. We never store a stock number. Every change is a new row in `txns`, and
   current stock is SUM(qty_base). That gives history, undo and an audit trail
   for free, and a wrong entry can be corrected rather than having already
   overwritten the truth.

2. Every row belongs to a shop. One deployment serves many shops, and a shop
   can only ever see its own rows - the shop id comes from a signed token, not
   from anything the caller sends us.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

import parse as nlu

DB = os.environ.get("DB_PATH", "sunobolo.db")
# Postgres when the host gives us one, SQLite otherwise. Free hosting wipes the
# filesystem on every restart, so a file-backed database there is not durable.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
if PG:
    import psycopg
    from psycopg.rows import dict_row
# ponytail: a process-lifetime secret is fine for one free-tier instance - a
# restart just signs everyone out. Set SECRET_KEY in the environment to keep
# sessions across restarts, and before ever running more than one instance.
SECRET = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
# A Google client id is PUBLIC by design - it is visible in the page source of
# every site that uses it. What actually protects it is the origin allowlist in
# the Google console, not secrecy, so keeping it here is fine. The environment
# variable overrides it for other deployments.
DEFAULT_GOOGLE_CLIENT_ID = (
    "781079652989-pgjep3a8i2llgt4476mvqaefk4ra9gk2.apps.googleusercontent.com")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", DEFAULT_GOOGLE_CLIENT_ID).strip()

SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_name  TEXT NOT NULL,
  owner_name TEXT NOT NULL,
  phone      TEXT UNIQUE,              -- phone+PIN accounts only (SQLite allows many NULLs)
  pin_hash   TEXT,                     -- salt$pbkdf2, never the PIN itself
  email      TEXT UNIQUE,              -- Google accounts only
  google_sub TEXT UNIQUE,              -- Google's stable user id, safer than email
  lang       TEXT DEFAULT 'hi',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id       INTEGER NOT NULL REFERENCES shops(id),
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
  shop_id    INTEGER NOT NULL REFERENCES shops(id),
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

CREATE INDEX IF NOT EXISTS idx_items_shop ON items(shop_id);
CREATE INDEX IF NOT EXISTS idx_txns_shop  ON txns(shop_id);
"""

# name, hi, te, base, packs, reorder, target, price, aliases, opening stock
# Every new shop starts with this catalogue so the app is useful from minute one.
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


class Cur:
    """Just enough cursor for psycopg to look like sqlite3's."""
    def __init__(self, cur, lastrowid=None):
        self._c, self.lastrowid = cur, lastrowid
    def fetchone(self): return self._c.fetchone()
    def fetchall(self): return self._c.fetchall()
    def __iter__(self): return iter(self._c)


class Conn:
    """One connection over two dialects.

    Only three things actually differ, so only three things are handled here:
    the placeholder character, how you learn the id of a row you just inserted,
    and running a multi-statement script. Every query in this file stays written
    once, in SQLite syntax.
    """
    def __init__(self, raw): self.raw = raw

    def execute(self, sql, args=()):
        if not PG:
            return self.raw.execute(sql, args)
        sql = sql.replace("?", "%s")
        if sql.lstrip()[:6].upper() == "INSERT" and "RETURNING" not in sql.upper():
            # psycopg has no lastrowid - ask Postgres for the id on the way in
            cur = self.raw.execute(sql + " RETURNING id", args)
            row = cur.fetchone()
            return Cur(cur, row["id"] if row else None)
        return Cur(self.raw.execute(sql, args))

    def executescript(self, sql):
        return self.raw.execute(sql) if PG else self.raw.executescript(sql)

    def commit(self): self.raw.commit()
    def close(self): self.raw.close()


def db():
    if PG:
        return Conn(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row        # rows behave like dicts
    return Conn(con)


def schema_sql():
    """The schema is written once in SQLite syntax; Postgres needs three swaps."""
    if not PG:
        return SCHEMA
    return (SCHEMA
            .replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            .replace("TEXT DEFAULT CURRENT_TIMESTAMP", "TIMESTAMPTZ DEFAULT now()")
            .replace(" REAL", " DOUBLE PRECISION"))


def setup():
    con = db()
    if PG:                               # a managed database starts empty
        con.executescript(schema_sql())
        con.commit()
        con.close()
        return
    # The single-shop version had no shop_id. Nothing in it was real data, so
    # starting the multi-shop schema clean is safer than guessing an owner.
    if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'").fetchone():
        cols = [c["name"] for c in con.execute("PRAGMA table_info(items)")]
        if "shop_id" not in cols:
            con.executescript("DROP TABLE IF EXISTS txns; DROP TABLE IF EXISTS items;")
    if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shops'").fetchone():
        cols = [c["name"] for c in con.execute("PRAGMA table_info(shops)")]
        if "google_sub" not in cols:
            # phone changed from NOT NULL to nullable, which SQLite cannot ALTER.
            # Only demo accounts exist at this point, so rebuild rather than guess.
            con.executescript("DROP TABLE IF EXISTS txns; DROP TABLE IF EXISTS items;"
                              "DROP TABLE IF EXISTS shops;")
    con.executescript(schema_sql())
    con.commit()
    con.close()


app = FastAPI(title="SunoBolo")
setup()


# ── accounts and sessions ────────────────────────────────────────────────────

def hash_pin(pin, salt=None):
    """PBKDF2, not a bare hash. A 4-digit PIN has only 10,000 possibilities, so
    the work factor is the only thing making a stolen database hard to use."""
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def check_pin(pin, stored):
    if not stored:                       # Google accounts have no PIN to check
        return False
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(stored, hash_pin(pin, salt))


def make_token(shop_id):
    """Signed and stateless - no sessions table to keep in step with anything."""
    sig = hmac.new(SECRET.encode(), str(shop_id).encode(), hashlib.sha256).hexdigest()
    return f"{shop_id}.{sig}"


def current_shop(authorization: str = Header(None)) -> int:
    """The shop id comes from the signature, never from the request body -
    otherwise any caller could read any shop by changing a number."""
    token = (authorization or "").replace("Bearer ", "").strip()
    try:
        shop_id, sig = token.split(".", 1)
        expected = hmac.new(SECRET.encode(), shop_id.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected):
            return int(shop_id)
    except (ValueError, AttributeError):
        pass
    raise HTTPException(401, "please sign in again")


def seed_shop(con, shop_id):
    """Give a brand new shop the starter catalogue so it is useful immediately."""
    for n, hi, te, bu, p, r, t, pr, a, opening in SEED:
        it = con.execute(
            "INSERT INTO items (shop_id,name,name_hi,name_te,base_unit,packs,"
            "reorder_level,target_level,last_price,aliases) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (shop_id, n, hi, te, bu, json.dumps(p), r, t, pr, json.dumps(a)))
        # Opening stock is itself a ledger row - there is no other way to have
        # stock, which is what keeps every number traceable.
        if opening:
            con.execute(
                "INSERT INTO txns (shop_id,item_id,qty,unit,qty_base,transcript,source)"
                " VALUES (?,?,?,?,?,'opening stock','seed')",
                (shop_id, it.lastrowid, opening, bu, opening))


def valid_pin(pin):
    return isinstance(pin, str) and pin.isdigit() and len(pin) == 4


@app.post("/register")
def register(body: dict):
    shop_name = (body.get("shop_name") or "").strip()
    owner = (body.get("owner_name") or "").strip()
    phone = "".join(ch for ch in str(body.get("phone") or "") if ch.isdigit())
    pin = str(body.get("pin") or "")

    if not shop_name or not owner:
        raise HTTPException(400, "shop name and owner name are required")
    if len(phone) != 10:
        raise HTTPException(400, "phone must be 10 digits")
    if not valid_pin(pin):
        raise HTTPException(400, "PIN must be 4 digits")

    con = db()
    if con.execute("SELECT 1 FROM shops WHERE phone=?", (phone,)).fetchone():
        con.close()
        raise HTTPException(409, "this phone number is already registered")

    cur = con.execute(
        "INSERT INTO shops (shop_name,owner_name,phone,pin_hash,lang) VALUES (?,?,?,?,?)",
        (shop_name, owner, phone, hash_pin(pin), body.get("lang") or "hi"))
    shop_id = cur.lastrowid

    seed_shop(con, shop_id)
    con.commit()
    con.close()
    return {"token": make_token(shop_id), "shop_name": shop_name,
            "owner_name": owner, "lang": body.get("lang") or "hi"}


@app.post("/login")
def login(body: dict):
    phone = "".join(ch for ch in str(body.get("phone") or "") if ch.isdigit())
    pin = str(body.get("pin") or "")
    con = db()
    row = con.execute("SELECT * FROM shops WHERE phone=?", (phone,)).fetchone()
    con.close()
    # One message for both failures - never reveal which numbers are registered.
    if not row or not check_pin(pin, row["pin_hash"]):
        raise HTTPException(401, "wrong phone number or PIN")
    return {"token": make_token(row["id"]), "shop_name": row["shop_name"],
            "owner_name": row["owner_name"], "lang": row["lang"]}


@app.get("/me")
def me(shop: int = Depends(current_shop)):
    con = db()
    row = con.execute("SELECT shop_name,owner_name,phone,email,lang,created_at"
                      " FROM shops WHERE id=?", (shop,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(401, "please sign in again")
    out = dict(row)
    out["items"] = con.execute(
        "SELECT COUNT(*) AS n FROM items WHERE shop_id=?", (shop,)).fetchone()["n"]
    out["entries"] = con.execute(
        "SELECT COUNT(*) AS n FROM txns WHERE shop_id=?", (shop,)).fetchone()["n"]
    con.close()
    return out


@app.get("/config")
def config():
    """What the frontend needs to know before anyone signs in. The client id is
    a public value; the Google button is simply hidden when it is not set."""
    return {"google_client_id": GOOGLE_CLIENT_ID}


@app.post("/auth/google")
def auth_google(body: dict):
    """Sign in (or sign up) with a Google account.

    The browser hands us an ID token. We do NOT trust it - we ask Google to
    verify it, and then check that the token was issued for OUR app. Without
    that `aud` check anyone could sign in here using a token minted for some
    other site, which is the classic way this integration is got wrong.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not set up on this server")
    credential = (body.get("credential") or "").strip()
    if not credential:
        raise HTTPException(400, "missing Google credential")

    try:
        r = httpx.get("https://oauth2.googleapis.com/tokeninfo",
                      params={"id_token": credential}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(503, "could not reach Google, try the PIN instead")
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in failed")
    info = r.json()

    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Google sign-in failed")
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Google sign-in failed")
    if str(info.get("email_verified", "")).lower() not in ("true", "1"):
        raise HTTPException(401, "this Google account has no verified email")

    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    name = info.get("given_name") or info.get("name") or email.split("@")[0]
    if not sub:
        raise HTTPException(401, "Google sign-in failed")

    con = db()
    row = con.execute("SELECT * FROM shops WHERE google_sub=?", (sub,)).fetchone()
    if not row and email:
        # Someone who registered with a phone, now signing in with Google on the
        # same verified email: link the accounts rather than making a second shop.
        row = con.execute("SELECT * FROM shops WHERE email=?", (email,)).fetchone()
        if row:
            con.execute("UPDATE shops SET google_sub=? WHERE id=?", (sub, row["id"]))
            con.commit()

    if row:
        con.close()
        return {"token": make_token(row["id"]), "shop_name": row["shop_name"],
                "owner_name": row["owner_name"], "lang": row["lang"], "needs_name": False}

    # New account. Google gives us a person, not a shop, so the shop still needs
    # a name - the frontend asks for it as a single follow-up step.
    cur = con.execute(
        "INSERT INTO shops (shop_name,owner_name,email,google_sub,lang) VALUES (?,?,?,?,?)",
        (f"{name}", name, email or None, sub, body.get("lang") or "hi"))
    shop_id = cur.lastrowid
    seed_shop(con, shop_id)
    con.commit()
    con.close()
    return {"token": make_token(shop_id), "shop_name": name, "owner_name": name,
            "lang": body.get("lang") or "hi", "needs_name": True}


@app.post("/shop/name")
def rename_shop(body: dict, shop: int = Depends(current_shop)):
    """Used right after a Google sign-up, and any time the owner wants to
    rename the shop."""
    name = (body.get("shop_name") or "").strip()
    if not name:
        raise HTTPException(400, "shop name is required")
    con = db()
    con.execute("UPDATE shops SET shop_name=? WHERE id=?", (name[:60], shop))
    con.commit()
    con.close()
    return {"shop_name": name[:60]}


# ── stock ────────────────────────────────────────────────────────────────────

def stock_rows(shop):
    """Every item with its current stock. The only place stock is computed."""
    con = db()
    rows = con.execute("""
        SELECT i.*, COALESCE(SUM(t.qty_base), 0) AS stock
        FROM items i LEFT JOIN txns t ON t.item_id = i.id
        WHERE i.shop_id = ?
        GROUP BY i.id ORDER BY i.name
    """, (shop,)).fetchall()
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
@app.head("/")                          # some hosts health-check with HEAD
def home():
    return FileResponse("index.html")


@app.get("/healthz")
def healthz():
    """Cheap liveness check that does not touch the database."""
    return {"ok": True}


@app.get("/stock")
def stock(shop: int = Depends(current_shop)):
    return stock_rows(shop)


@app.post("/parse")
def do_parse(body: dict, shop: int = Depends(current_shop)):
    """Read-only on purpose. Nothing here touches the database - the user has
    to approve a movement before it becomes real."""
    moves = nlu.parse(body.get("text", ""), stock_rows(shop), body.get("mode", "command"))
    for m in moves:                       # trim the item down for the wire
        if "item" in m:
            m["item"] = {k: m["item"][k] for k in
                         ("id", "name", "name_hi", "name_te", "base_unit", "packs", "stock")}
        m["candidates"] = [{"id": c["id"], "name": c["name"],
                            "name_hi": c["name_hi"], "name_te": c["name_te"]}
                           for c in m.get("candidates", [])]
    return {"moves": moves, "lang": body.get("lang", "hi")}


@app.post("/commit")
def commit(body: dict, shop: int = Depends(current_shop)):
    """The only endpoint that writes. One approved movement -> one ledger row."""
    item = next((i for i in stock_rows(shop) if i["id"] == body.get("item_id")), None)
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
        "INSERT INTO txns (shop_id,item_id,qty,unit,qty_base,transcript,lang,confidence,source)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (shop, item["id"], qty, unit, qty_base, body.get("transcript"), body.get("lang"),
         body.get("confidence"), body.get("source", "command")))
    con.commit()
    txn_id = cur.lastrowid
    con.close()
    return {"txn_id": txn_id, "item": item["name"],
            "applied": qty_base, "new_total": round(item["stock"] + qty_base, 2),
            "base_unit": item["base_unit"]}


@app.post("/undo/{txn_id}")
def undo(txn_id: int, shop: int = Depends(current_shop)):
    """Reverse a movement by adding the opposite row. We never delete history."""
    con = db()
    t = con.execute("SELECT * FROM txns WHERE id=? AND shop_id=?", (txn_id, shop)).fetchone()
    if not t:
        con.close()
        raise HTTPException(404, "unknown entry")
    con.execute(
        "INSERT INTO txns (shop_id,item_id,qty,unit,qty_base,transcript,lang,source)"
        " VALUES (?,?,?,?,?,?,?,'undo')",
        (shop, t["item_id"], t["qty"], t["unit"], -t["qty_base"],
         f"undo of #{txn_id}", t["lang"]))
    con.commit()
    con.close()
    return {"ok": True}


@app.get("/search")
def search(q: str = "", shop: int = Depends(current_shop)):
    """Find an item by ANY alias in ANY language: 'rice', 'chawal' and 'बियाम'
    all reach the same row. This is the escape hatch when a match is wrong."""
    q = q.strip().lower()
    rows = stock_rows(shop)
    if not q:
        return rows
    return [i for i in rows
            if q in i["name"].lower() or any(q in a.lower() for a in i["aliases"])]


@app.post("/items")
def add_item(body: dict, shop: int = Depends(current_shop)):
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
        "INSERT INTO items (shop_id,name,name_hi,name_te,aliases,base_unit,packs,"
        "reorder_level,target_level,last_price) VALUES (?,?,?,?,?,?,'{}',?,?,0)",
        (shop, name, name, name, json.dumps(aliases), base,
         float(body.get("reorder_level") or 0), float(body.get("target_level") or 0)))
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return {"id": new_id, "name": name, "base_unit": base}


@app.post("/items/{item_id}/alias")
def learn_alias(item_id: int, body: dict, shop: int = Depends(current_shop)):
    """THE LEARNING STEP. Every correction teaches the lexicon.

    When the owner says "tamatar" and fixes the match to Tomato, that word is
    stored as an alias of Tomato. Correct it once; it is right from then on.
    This is why the system gets better with use without any training."""
    word = (body.get("word") or "").strip().lower()
    if not word:
        return {"learned": False}
    con = db()
    row = con.execute("SELECT aliases FROM items WHERE id=? AND shop_id=?",
                      (item_id, shop)).fetchone()
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
def alerts(shop: int = Depends(current_shop)):
    """Low stock, with how much to order expressed in the unit you actually buy in."""
    out = []
    for i in stock_rows(shop):
        if i["status"] == "ok":
            continue
        need = i["target_level"] - i["stock"]
        unit, factor = next(iter(i["packs"].items()), (i["base_unit"], 1))
        out.append({**i, "need": round(need, 1),
                    "order_qty": max(1, round(need / factor)), "order_unit": unit})
    return out


@app.get("/item/{item_id}")
def item(item_id: int, shop: int = Depends(current_shop)):
    i = next((x for x in stock_rows(shop) if x["id"] == item_id), None)
    if not i:
        raise HTTPException(404, "unknown item")
    con = db()
    i["history"] = [dict(r) for r in con.execute(
        "SELECT * FROM txns WHERE item_id=? AND shop_id=? ORDER BY id DESC LIMIT 15",
        (item_id, shop))]
    con.close()
    return i


@app.get("/export.csv", response_class=PlainTextResponse)
def export(shop: int = Depends(current_shop)):
    """Backup. The owner's data should never be locked inside our database."""
    con = db()
    rows = con.execute(
        "SELECT t.id,t.created_at,i.name,t.qty,t.unit,t.qty_base,t.source,t.transcript"
        " FROM txns t JOIN items i ON i.id=t.item_id WHERE t.shop_id=? ORDER BY t.id",
        (shop,)).fetchall()
    con.close()
    lines = ["id,when,item,qty,unit,change,source,heard"]
    lines += [",".join(f'"{v}"' for v in r) for r in rows]
    return "\n".join(lines)
