"""Run with:  python test_auth.py

The one thing that must never break in a multi-shop app: one shop must not be
able to see or touch another shop's stock.
"""
import os
os.environ["DB_PATH"] = "test_auth.db"
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

    # each starts with its own copy of the catalogue
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

    print("all 22 auth checks passed")


if __name__ == "__main__":
    run()
