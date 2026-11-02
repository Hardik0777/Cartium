import hashlib
import hmac
from datetime import timedelta

import pytest

from app.core.config import settings
from app.models import Order, OrderStatus, Product
from app.services import razorpay

SECRET = "test_secret_for_signatures"
REAL_CREATE_ORDER = razorpay.create_order  # saved before the fixture swaps it for a stub
ADDRESS = {"full_name": "Hardik A", "phone": "9876543210", "line1": "12 Mall Road",
           "city": "Karnal", "state": "Haryana", "pincode": "132001"}


@pytest.fixture(autouse=True)
def fake_razorpay(monkeypatch):
    """Razorpay's API is replaced by a stub; signatures are made exactly the way Razorpay makes them."""
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_dummy")
    monkeypatch.setattr(settings, "razorpay_key_secret", SECRET)
    created = []

    def create_order(amount_paise, receipt):
        created.append(amount_paise)
        return f"order_test{len(created)}"

    monkeypatch.setattr(razorpay, "create_order", create_order)
    return created


def sign(order_id, payment_id, secret=SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


@pytest.fixture()
def ready(client, catalog, make_user, login):
    """A buyer with an address and a cart holding 2 kettles (₹899 each) and 1 earbuds (₹2,499)."""
    make_user(email="b@test.dev")
    h = login("b@test.dev")
    address = client.post("/api/account/addresses", json=ADDRESS, headers=h).json()
    client.post("/api/cart", json={"product_id": catalog["kettle"], "quantity": 2}, headers=h)
    cart = client.post("/api/cart", json={"product_id": catalog["earbuds"]}, headers=h).json()
    return {"h": h, "cart": cart["id"], "address": address["id"]}


def stock(db_session, pid):
    with db_session() as db:
        return db.get(Product, pid).stock


def checkout(client, ready):
    return client.post("/api/orders/razorpay/create", json={"cart_id": ready["cart"], "address_id": ready["address"]},
                       headers=ready["h"])


def test_checkout_charges_server_computed_total_and_reserves_stock(client, catalog, ready, fake_razorpay, db_session):
    res = checkout(client, ready)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["amount"] == (2 * 899 + 2499) * 100 == fake_razorpay[0]  # paise
    assert body["key_id"] == "rzp_test_dummy" and body["contact"] == "9876543210"
    assert stock(db_session, catalog["kettle"]) == 8 and stock(db_session, catalog["earbuds"]) == 9


def test_valid_payment_marks_paid_and_empties_cart(client, catalog, ready):
    co = checkout(client, ready).json()
    res = client.post("/api/orders/razorpay/verify", headers=ready["h"], json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "pay_123",
        "razorpay_signature": sign(co["razorpay_order_id"], "pay_123")})
    assert res.status_code == 200
    order = res.json()
    assert order["status"] == "paid" and order["progress"] == "placed" and order["total"] == 4297
    assert "Karnal" in order["ship_address"] and len(order["items"]) == 2
    assert client.get("/api/cart", headers=ready["h"]).json()["lines"] == []
    assert [o["id"] for o in client.get("/api/orders", headers=ready["h"]).json()] == [co["order_id"]]
    # Verifying again is harmless.
    again = client.post("/api/orders/razorpay/verify", headers=ready["h"], json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "pay_123",
        "razorpay_signature": sign(co["razorpay_order_id"], "pay_123")})
    assert again.status_code == 200


def test_forged_signature_is_rejected(client, ready):
    co = checkout(client, ready).json()
    res = client.post("/api/orders/razorpay/verify", headers=ready["h"], json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "pay_123",
        "razorpay_signature": sign(co["razorpay_order_id"], "pay_123", secret="attacker-guess")})
    assert res.status_code == 400
    assert client.get(f"/api/orders/{co['order_id']}", headers=ready["h"]).json()["status"] == "pending_payment"


def test_cancel_returns_stock(client, catalog, ready, db_session):
    co = checkout(client, ready).json()
    assert client.post(f"/api/orders/{co['order_id']}/cancel", headers=ready["h"]).json()["status"] == "cancelled"
    assert stock(db_session, catalog["kettle"]) == 10
    assert client.post(f"/api/orders/{co['order_id']}/cancel", headers=ready["h"]).status_code == 409


def test_expired_reservation_is_released(client, catalog, ready, db_session):
    co = checkout(client, ready).json()
    with db_session() as db:
        order = db.get(Order, co["order_id"])
        order.expires_at = order.expires_at - timedelta(hours=1)
        db.commit()
    client.get("/api/orders", headers=ready["h"])  # triggers the lazy cleanup
    assert stock(db_session, catalog["kettle"]) == 10
    with db_session() as db:
        assert db.get(Order, co["order_id"]).status == OrderStatus.cancelled


def test_cannot_checkout_more_than_stock(client, catalog, ready, db_session):
    with db_session() as db:
        db.get(Product, catalog["kettle"]).stock = 1  # someone else bought them meanwhile
        db.commit()
    res = checkout(client, ready)
    assert res.status_code == 409 and "Electric Kettle" in res.json()["detail"]


def test_payments_not_configured_gives_clear_error(client, ready, monkeypatch, db_session, catalog):
    monkeypatch.setattr(settings, "razorpay_key_secret", "")
    monkeypatch.setattr(razorpay, "create_order", REAL_CREATE_ORDER)
    res = checkout(client, ready)
    assert res.status_code == 503 and "RAZORPAY" in res.json()["detail"]
    assert stock(db_session, catalog["kettle"]) == 10  # nothing stays reserved


def test_other_buyers_cannot_see_or_pay_my_order(client, ready, make_user, login):
    co = checkout(client, ready).json()
    make_user(email="x@test.dev")
    x = login("x@test.dev")
    assert client.get(f"/api/orders/{co['order_id']}", headers=x).status_code == 404
    res = client.post("/api/orders/razorpay/verify", headers=x, json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "p",
        "razorpay_signature": sign(co["razorpay_order_id"], "p")})
    assert res.status_code == 404


def test_reorder_adds_available_items_and_skips_others(client, catalog, ready, db_session):
    co = checkout(client, ready).json()
    client.post("/api/orders/razorpay/verify", headers=ready["h"], json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "p1",
        "razorpay_signature": sign(co["razorpay_order_id"], "p1")})
    with db_session() as db:
        db.get(Product, catalog["earbuds"]).stock = 0
        db.commit()
    res = client.post(f"/api/orders/{co['order_id']}/reorder", headers=ready["h"]).json()
    assert res["added"] == ["Electric Kettle"] and res["skipped"] == ["Wireless Earbuds"]
    assert client.get("/api/cart", headers=ready["h"]).json()["lines"][0]["quantity"] == 2


def test_order_keeps_price_paid_even_if_listing_changes(client, catalog, ready, db_session):
    co = checkout(client, ready).json()
    with db_session() as db:
        db.get(Product, catalog["kettle"]).price = 5000
        db.commit()
    order = client.get(f"/api/orders/{co['order_id']}", headers=ready["h"]).json()
    assert {i["name"]: i["unit_price"] for i in order["items"]}["Electric Kettle"] == 899


def test_two_buyers_racing_for_the_last_unit(client, catalog, make_user, login, db_session):
    """Both buyers check out the last unit at the same moment; exactly one may get it.
    Only meaningful on MySQL, where SELECT ... FOR UPDATE really locks rows."""
    import os
    import threading

    if not os.getenv("TEST_DATABASE_URL", "").startswith("mysql"):
        pytest.skip("row locks need MySQL")
    pid = catalog["kettle"]
    with db_session() as db:
        db.get(Product, pid).stock = 1
        db.commit()
    jobs = []
    for n in range(2):
        make_user(email=f"r{n}@test.dev")
        h = login(f"r{n}@test.dev")
        addr = client.post("/api/account/addresses", json=ADDRESS, headers=h).json()["id"]
        cart = client.post("/api/cart", json={"product_id": pid}, headers=h).json()["id"]
        jobs.append((h, cart, addr))

    results, start = [], threading.Barrier(2)

    def go(h, cart, addr):
        start.wait()  # release both requests together
        results.append(client.post("/api/orders/razorpay/create", json={"cart_id": cart, "address_id": addr},
                                   headers=h).status_code)

    threads = [threading.Thread(target=go, args=job) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409]
    assert stock(db_session, pid) == 0
