import hashlib
import hmac

import pytest

from app.core.config import settings
from app.models import Product, Role, SellerStatus
from app.services import razorpay

ADDRESS = {"full_name": "Buyer", "phone": "9876543210", "line1": "1 Road", "city": "Karnal", "state": "Haryana", "pincode": "132001"}


@pytest.fixture()
def admin(client, catalog, make_user, login):
    make_user(email="admin@test.dev", role=Role.admin)
    return login("admin@test.dev")


@pytest.fixture()
def payments(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_x")
    monkeypatch.setattr(settings, "razorpay_key_secret", "s3cret")
    monkeypatch.setattr(razorpay, "create_order", lambda amount, receipt: f"order_{receipt}")
    refunds = []

    def refund(payment_id, amount_paise, note):
        refunds.append((payment_id, amount_paise))
        return f"rfnd_{len(refunds)}"

    monkeypatch.setattr(razorpay, "refund_payment", refund)
    return refunds


def buy(client, make_user, login, catalog, email="buyer@test.dev", items=(("earbuds", 1),)):
    make_user(email=email)
    h = login(email)
    addr = client.post("/api/account/addresses", json=ADDRESS, headers=h).json()["id"]
    cart = None
    for key, qty in items:
        cart = client.post("/api/cart", json={"product_id": catalog[key], "quantity": qty}, headers=h).json()["id"]
    co = client.post("/api/orders/razorpay/create", json={"cart_id": cart, "address_id": addr}, headers=h).json()
    sig = hmac.new(b"s3cret", f"{co['razorpay_order_id']}|pay_{email}".encode(), hashlib.sha256).hexdigest()
    client.post("/api/orders/razorpay/verify", headers=h, json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": f"pay_{email}", "razorpay_signature": sig})
    return h, co["order_id"]


def test_only_admins_get_in(client, catalog, login):
    assert client.get("/api/admin/dashboard", headers=login("good@test.dev")).status_code == 403


def test_approve_pending_seller_unlocks_selling(client, admin, make_user, login):
    make_user(email="new@test.dev", role=Role.seller, seller_status=SellerStatus.pending)
    seller = login("new@test.dev")
    assert client.get("/api/seller/dashboard", headers=seller).status_code == 403
    pending = client.get("/api/admin/users", params={"seller_status": "pending"}, headers=admin).json()
    uid = next(u["id"] for u in pending if u["email"] == "new@test.dev")
    assert client.patch(f"/api/admin/users/{uid}", json={"seller_status": "approved"}, headers=admin).status_code == 200
    assert client.get("/api/seller/dashboard", headers=seller).status_code == 200


def test_suspending_seller_hides_their_products_everywhere(client, admin, catalog):
    good = next(u for u in client.get("/api/admin/users", params={"q": "good@"}, headers=admin).json())
    client.patch(f"/api/admin/users/{good['id']}", json={"seller_status": "suspended", "note": "Fake reviews"}, headers=admin)
    assert client.get("/api/products").json()["total"] == 0
    assert client.get(f"/api/products/{catalog['earbuds']}").status_code == 404


def test_ban_logs_user_out_immediately_and_blocks_login(client, admin, make_user, login):
    make_user(email="banned@test.dev")
    h = login("banned@test.dev")
    uid = client.get("/api/admin/users", params={"q": "banned@"}, headers=admin).json()[0]["id"]
    client.patch(f"/api/admin/users/{uid}", json={"is_active": False, "note": "Abuse"}, headers=admin)
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"email": "banned@test.dev", "password": "Passw0rd!"}).status_code == 403


def test_admin_cannot_ban_or_demote_self(client, admin):
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}, headers=admin).status_code == 409
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "buyer"}, headers=admin).status_code == 409


def test_making_buyer_a_seller_starts_pending(client, admin, make_user, login):
    make_user(email="b@test.dev")
    uid = client.get("/api/admin/users", params={"q": "b@test"}, headers=admin).json()[0]["id"]
    row = client.patch(f"/api/admin/users/{uid}", json={"role": "seller"}, headers=admin).json()
    assert row["role"] == "seller" and row["seller_status"] == "pending"


def test_listing_moderation_with_reason_shown_to_seller(client, admin, catalog, login):
    queue = client.get("/api/admin/products", headers=admin).json()
    assert [p["name"] for p in queue] == ["Unreviewed Gadget"]
    assert client.patch(f"/api/admin/products/{catalog['pending']}/moderation", json={"status": "rejected"}, headers=admin).status_code == 422
    client.patch(f"/api/admin/products/{catalog['pending']}/moderation",
                 json={"status": "rejected", "note": "Add a real photo and a description"}, headers=admin)
    mine = {p["name"]: p for p in client.get("/api/seller/products", headers=login("good@test.dev")).json()}
    assert mine["Unreviewed Gadget"]["status"] == "rejected"
    assert mine["Unreviewed Gadget"]["moderation_note"] == "Add a real photo and a description"
    client.patch(f"/api/admin/products/{catalog['pending']}/moderation", json={"status": "approved"}, headers=admin)
    assert client.get(f"/api/products/{catalog['pending']}").status_code == 200


def test_seller_cancel_creates_refund_that_admin_sends_once(client, admin, catalog, make_user, login, payments):
    _, order_id = buy(client, make_user, login, catalog, items=(("earbuds", 2),))
    seller = login("good@test.dev")
    item = client.get("/api/seller/orders", headers=seller).json()[0]
    client.patch(f"/api/seller/orders/items/{item['id']}/status", json={"status": "cancelled"}, headers=seller)
    queue = client.get("/api/admin/refunds", headers=admin).json()
    assert len(queue) == 1 and queue[0]["amount"] == 2 * 2499 and queue[0]["order_id"] == order_id
    done = client.patch(f"/api/admin/refunds/{queue[0]['id']}", json={"action": "process"}, headers=admin)
    assert done.status_code == 200 and done.json()["status"] == "processed" and done.json()["razorpay_refund_id"] == "rfnd_1"
    assert payments == [("pay_buyer@test.dev", 499800)]
    again = client.patch(f"/api/admin/refunds/{queue[0]['id']}", json={"action": "process"}, headers=admin)
    assert again.status_code == 409 and len(payments) == 1  # never refunded twice


def test_refund_rejection_needs_a_note(client, admin, catalog, make_user, login, payments):
    buy(client, make_user, login, catalog)
    seller = login("good@test.dev")
    item = client.get("/api/seller/orders", headers=seller).json()[0]
    client.patch(f"/api/seller/orders/items/{item['id']}/status", json={"status": "cancelled"}, headers=seller)
    rid = client.get("/api/admin/refunds", headers=admin).json()[0]["id"]
    assert client.patch(f"/api/admin/refunds/{rid}", json={"action": "reject"}, headers=admin).status_code == 422


def test_complaint_flow(client, admin, catalog, make_user, login, payments):
    h, order_id = buy(client, make_user, login, catalog)
    body = {"subject": "Box was damaged", "message": "The earbuds case arrived cracked."}
    assert client.post(f"/api/orders/{order_id}/complaints", json=body, headers=h).status_code == 201
    assert client.post(f"/api/orders/{order_id}/complaints", json=body, headers=h).status_code == 409  # one open at a time
    c = client.get("/api/admin/complaints", headers=admin).json()[0]
    client.patch(f"/api/admin/complaints/{c['id']}", json={"reply": "Sorry! A replacement is on its way."}, headers=admin)
    mine = client.get(f"/api/orders/{order_id}/complaints", headers=h).json()[0]
    assert mine["status"] == "resolved" and mine["admin_reply"].startswith("Sorry")


def test_other_buyers_cannot_complain_about_my_order(client, catalog, make_user, login, payments):
    _, order_id = buy(client, make_user, login, catalog)
    make_user(email="x@test.dev")
    res = client.post(f"/api/orders/{order_id}/complaints", json={"subject": "Hello", "message": "Not my order at all"},
                      headers=login("x@test.dev"))
    assert res.status_code == 404


def test_dashboard_numbers_flags_and_audit_log(client, admin, catalog, make_user, login, payments, db_session):
    with db_session() as db:
        db.get(Product, catalog["earbuds"]).price = 26000  # a high-value order
        db.commit()
    buy(client, make_user, login, catalog)
    good = client.get("/api/admin/users", params={"q": "good@"}, headers=admin).json()[0]
    client.patch(f"/api/admin/users/{good['id']}", json={"seller_status": "approved", "note": "Verified GST"}, headers=admin)
    d = client.get("/api/admin/dashboard", headers=admin).json()
    assert d["paid_orders"] == 1 and d["gmv"] == 26000 and d["pending_listings"] == 1
    assert d["last_14_days"][-1]["orders"] == 1 and len(d["last_14_days"]) == 14
    assert [f["kind"] for f in d["flags"]] == ["high_value_order"]
    assert d["recent_actions"][0]["action"] == "seller:approved" and d["recent_actions"][0]["note"] == "Verified GST"


def test_paying_after_expiry_queues_full_refund(client, admin, catalog, make_user, login, payments, db_session):
    from datetime import timedelta

    from app.models import Order
    make_user(email="late@test.dev")
    h = login("late@test.dev")
    addr = client.post("/api/account/addresses", json=ADDRESS, headers=h).json()["id"]
    cart = client.post("/api/cart", json={"product_id": catalog["kettle"]}, headers=h).json()["id"]
    co = client.post("/api/orders/razorpay/create", json={"cart_id": cart, "address_id": addr}, headers=h).json()
    with db_session() as db:
        o = db.get(Order, co["order_id"])
        o.expires_at = o.expires_at - timedelta(hours=1)
        db.commit()
    client.get("/api/orders", headers=h)  # expiry cleanup runs
    sig = hmac.new(b"s3cret", f"{co['razorpay_order_id']}|pay_late".encode(), hashlib.sha256).hexdigest()
    res = client.post("/api/orders/razorpay/verify", headers=h, json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "pay_late", "razorpay_signature": sig})
    assert res.status_code == 409 and "refunded" in res.json()["detail"]
    queue = client.get("/api/admin/refunds", headers=admin).json()
    assert queue[0]["amount"] == 899 and queue[0]["razorpay_payment_id"] == "pay_late"
