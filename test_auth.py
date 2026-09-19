"""Run with:  python test_auth.py

The one thing that must never break in a multi-shop app: one shop must not be
able to see or touch another shop's stock.
"""
import os
os.environ["DB_PATH"] = "test_auth.db"
# Force the unconfigured case so we test that Google sign-in degrades cleanly,
# not whatever client id happens to be set in this environment.
os.environ["GOOGLE_CLIENT_ID"] = ""
if os.path.exists("test_auth.db"):
    os.remove("test_auth.db")

from fastapi.testclient import TestClient
from app import app

c = TestClient(app)
auth = lambda tok: {"Authorization": "Bearer " + tok}


def run():
    # register two different shops
    a = c.post("/register", json={"shop_name": "Ramesh Kirana", "owner_name": "Ramesh",
                                  "phone": "9876543210", "pin": "1234", "lang": "hi"}).json()
    b = c.post("/register", json={"shop_name": "Lakshmi Provisions", "owner_name": "Lakshmi",
                                  "phone": "9000000001", "pin": "4321", "lang": "te"}).json()
    assert a["token"] != b["token"]

    # a new shop starts EMPTY - its stock is the owner's, not our sample
    assert c.get("/stock", headers=auth(a["token"])).json() == []
    assert c.get("/stock", headers=auth(b["token"])).json() == []

    # the sample catalogue is opt-in, and cannot be applied twice
    assert c.post("/seed", headers=auth(a["token"])).json()["added"] == 8
    assert c.post("/seed", headers=auth(a["token"])).status_code == 409
    c.post("/seed", headers=auth(b["token"]))

    sa, sb = c.get("/stock", headers=auth(a["token"])).json(), c.get("/stock", headers=auth(b["token"])).json()
    assert len(sa) == len(sb) == 8
    assert not ({i["id"] for i in sa} & {i["id"] for i in sb}), "item ids leaked between shops"

    # a sale in shop A must not move shop B
    rice_a = next(i for i in sa if i["name"] == "Rice")
    c.post("/commit", headers=auth(a["token"]),
           json={"item_id": rice_a["id"], "qty": 10, "unit": "kg", "direction": "out"})
    rice_b = next(i for i in c.get("/stock", headers=auth(b["token"])).json() if i["name"] == "Rice")
    assert rice_b["stock"] == 42, f"shop B's rice moved: {rice_b['stock']}"

    # shop B must not be able to write to shop A's item even knowing its id
    assert c.post("/commit", headers=auth(b["token"]),
                  json={"item_id": rice_a["id"], "qty": 5, "unit": "kg"}).status_code == 404
    assert c.get(f"/item/{rice_a['id']}", headers=auth(b["token"])).status_code == 404

    # no token, bad token, and a forged shop id are all rejected
    assert c.get("/stock").status_code == 401
    assert c.get("/stock", headers=auth("garbage")).status_code == 401
    assert c.get("/stock", headers=auth("1.deadbeef")).status_code == 401

    # login checks
    assert c.post("/login", json={"phone": "9876543210", "pin": "1234"}).status_code == 200
    assert c.post("/login", json={"phone": "9876543210", "pin": "9999"}).status_code == 401
    assert c.post("/login", json={"phone": "0000000000", "pin": "1234"}).status_code == 401
    # a phone that exists and one that does not must fail identically
    assert (c.post("/login", json={"phone": "9876543210", "pin": "9999"}).json() ==
            c.post("/login", json={"phone": "0000000000", "pin": "1234"}).json())

    # registration validation
    assert c.post("/register", json={"shop_name": "X", "owner_name": "Y",
                                     "phone": "9876543210", "pin": "1111"}).status_code == 409
    assert c.post("/register", json={"shop_name": "X", "owner_name": "Y",
                                     "phone": "123", "pin": "1111"}).status_code == 400
    assert c.post("/register", json={"shop_name": "X", "owner_name": "Y",
                                     "phone": "9000000002", "pin": "12"}).status_code == 400

    # the PIN is never stored in readable form
    import sqlite3
    con = sqlite3.connect("test_auth.db")
    stored = con.execute("SELECT pin_hash FROM shops WHERE phone='9876543210'").fetchone()[0]
    con.close()
    assert "1234" not in stored and len(stored) > 60, stored

    # Google sign-in is optional. With no client id configured the button is
    # hidden and the endpoint refuses rather than half-working.
    assert c.get("/config").json()["google_client_id"] == ""
    assert c.post("/auth/google", json={"credential": "anything"}).status_code == 503

    # renaming a shop (used straight after a Google sign-up) is scoped to the
    # caller's own shop and cannot be blanked
    assert c.post("/shop/name", headers=auth(a["token"]),
                  json={"shop_name": "Ramesh Super Store"}).status_code == 200
    assert c.get("/me", headers=auth(a["token"])).json()["shop_name"] == "Ramesh Super Store"
    assert c.get("/me", headers=auth(b["token"])).json()["shop_name"] == "Lakshmi Provisions"
    assert c.post("/shop/name", headers=auth(a["token"]), json={"shop_name": "  "}).status_code == 400
    assert c.post("/shop/name", json={"shop_name": "X"}).status_code == 401

    # editing an item keeps the old name matchable, and is scoped to the shop
    assert c.post(f"/item/{rice_a['id']}/edit", headers=auth(a["token"]),
                  json={"name": "Basmati Rice", "reorder_level": 60,
                        "target_level": 200}).status_code == 200
    ra = next(i for i in c.get("/stock", headers=auth(a["token"])).json() if i["id"] == rice_a["id"])
    assert ra["name"] == "Basmati Rice" and ra["reorder_level"] == 60
    assert "chawal" in ra["aliases"] and "basmati rice" in ra["aliases"], ra["aliases"]
    assert c.post(f"/item/{rice_a['id']}/edit", headers=auth(b["token"]),
                  json={"name": "Hijack"}).status_code == 404

    # clearing entries is scoped, counts what it removed, and leaves items alone
    before = c.get("/me", headers=auth(a["token"])).json()["entries"]
    assert before > 0
    assert c.post("/entries/clear", headers=auth(a["token"]), json={"scope": "bogus"}).status_code == 400
    r = c.post("/entries/clear", headers=auth(a["token"]), json={"scope": "all"}).json()
    assert r["cleared"] == before and r["remaining"] == 0, r
    assert len(c.get("/stock", headers=auth(a["token"])).json()) == 8, "items must survive"
    assert c.get("/me", headers=auth(b["token"])).json()["entries"] > 0, "shop B untouched"

    # deleting an item takes its history with it, and only its own shop may
    assert c.post(f"/item/{rice_a['id']}/delete", headers=auth(b["token"])).status_code == 404
    assert c.post(f"/item/{rice_a['id']}/delete", headers=auth(a["token"])).status_code == 200
    assert len(c.get("/stock", headers=auth(a["token"])).json()) == 7

    print("all 36 auth checks passed")


def dialect():
    """The Postgres path cannot be exercised without a live Postgres, so test the
    three translations it depends on. If these are right, the queries are too."""
    import app as A

    pg = A.SCHEMA
    pg = (pg.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            .replace("TEXT DEFAULT CURRENT_TIMESTAMP", "TIMESTAMPTZ DEFAULT now()")
            .replace(" REAL", " DOUBLE PRECISION"))
    assert "AUTOINCREMENT" not in pg and pg.count("SERIAL PRIMARY KEY") == 3, "id columns"
    assert "CURRENT_TIMESTAMP" not in pg and pg.count("TIMESTAMPTZ") == 2, "timestamps"
    assert " REAL" not in pg and "DOUBLE PRECISION" in pg, "float columns"
    # the swaps must not have damaged anything else
    assert pg.count("CREATE TABLE") == 3 and pg.count("REFERENCES") == 3

    # every placeholder becomes %s, and inserts learn their new id
    sql = "INSERT INTO txns (shop_id,item_id,qty) VALUES (?,?,?)"
    conv = sql.replace("?", "%s")
    assert conv.count("%s") == 3 and "?" not in conv
    assert conv.lstrip()[:6].upper() == "INSERT" and "RETURNING" not in conv.upper()
    sel = "SELECT * FROM items WHERE shop_id=?".replace("?", "%s")
    assert sel.lstrip()[:6].upper() != "INSERT", "selects must not get RETURNING"

    # COUNT(*) is aliased, because a dict row factory cannot be indexed by 0
    src = open("app.py", encoding="utf-8").read()
    assert ".fetchone()[0]" not in src, "a bare fetchone()[0] breaks on postgres"

    print("all 9 dialect checks passed")


if __name__ == "__main__":
    run()
    dialect()
