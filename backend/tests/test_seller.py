import hashlib
import hmac

import pytest

from app.core.config import settings
from app.models import ListingStatus, Product, Role, SellerStatus
from app.services import razorpay

LISTING = {"name": "Steel Lunch Box", "brand": "Tiffin Co", "description": "Three tiers", "category_id": 1,
           "price": 499, "mrp": 799, "stock": 20, "low_stock_threshold": 3}


@pytest.fixture()
def seller(login, catalog):
    return login("good@test.dev")


def test_pending_seller_is_locked_out(client, make_user, login):
    make_user(email="new@test.dev", role=Role.seller, seller_status=SellerStatus.pending)
    assert client.get("/api/seller/dashboard", headers=login("new@test.dev")).status_code == 403


def test_create_listing_waits_for_review_and_is_hidden(client, seller):
    res = client.post("/api/seller/products", json=LISTING, headers=seller)
    assert res.status_code == 201 and res.json()["status"] == "pending"
    assert client.get(f"/api/products/{res.json()['id']}").status_code == 404
    mine = client.get("/api/seller/products", headers=seller).json()
    assert "Steel Lunch Box" in [p["name"] for p in mine] and "Unreviewed Gadget" in [p["name"] for p in mine]


def test_listing_validation(client, seller):
    assert client.post("/api/seller/products", json={**LISTING, "price": 900}, headers=seller).status_code == 422
    assert client.post("/api/seller/products", json={**LISTING, "category_id": 999}, headers=seller).status_code == 422
    bad = client.post("/api/seller/products", json={**LISTING, "image_url": "javascript:alert(1)"}, headers=seller)
    assert bad.status_code == 422


def test_edit_keeps_approval_and_other_sellers_cannot_touch(client, seller, catalog, make_user, login):
    res = client.patch(f"/api/seller/products/{catalog['earbuds']}", json={**LISTING, "name": "Earbuds v2"}, headers=seller)
    assert res.status_code == 200 and res.json()["status"] == "approved"
    assert client.get(f"/api/products/{catalog['earbuds']}").json()["name"] == "Earbuds v2"
    make_user(email="other@test.dev", role=Role.seller, seller_status=SellerStatus.approved)
    other = login("other@test.dev")
    assert client.patch(f"/api/seller/products/{catalog['earbuds']}", json=LISTING, headers=other).status_code == 404
    assert client.delete(f"/api/seller/products/{catalog['earbuds']}", headers=other).status_code == 404


def test_editing_rejected_listing_resubmits_it(client, seller, catalog, db_session):
    with db_session() as db:
        db.get(Product, catalog["pending"]).status = ListingStatus.rejected
        db.commit()
    res = client.patch(f"/api/seller/products/{catalog['pending']}", json=LISTING, headers=seller)
    assert res.json()["status"] == "pending"


def test_upload_accepts_real_images_only(client, seller):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    ok = client.post("/api/seller/uploads", files={"file": ("p.png", png, "image/png")}, headers=seller)
    assert ok.status_code == 201 and ok.json()["url"].startswith("/uploads/") and ok.json()["url"].endswith(".png")
    assert client.get(ok.json()["url"]).content == png
    from app.services.uploads import UPLOAD_DIR
    (UPLOAD_DIR / ok.json()["url"].rsplit("/", 1)[1]).unlink()  # don't leave test files behind
    fake = client.post("/api/seller/uploads", files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")}, headers=seller)
    assert fake.status_code == 415
    big = client.post("/api/seller/uploads", files={"file": ("big.png", png + b"0" * (2 * 1024 * 1024), "image/png")}, headers=seller)
    assert big.status_code == 413


# ------------------------------------------------------------ orders and dashboard
@pytest.fixture()
def paid_order(client, catalog, make_user, login, monkeypatch):
    """A buyer paid for 2 earbuds and 1 kettle, both from the 'good' seller."""
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_x")
    monkeypatch.setattr(settings, "razorpay_key_secret", "s3cret")
    monkeypatch.setattr(razorpay, "create_order", lambda amount, receipt: f"order_{receipt}")
    make_user(email="buyer@test.dev")
    h = login("buyer@test.dev")
    addr = client.post("/api/account/addresses", headers=h, json={
        "full_name": "Buyer", "phone": "9876543210", "line1": "1 Road", "city": "Karnal", "state": "Haryana", "pincode": "132001"}).json()["id"]
    client.post("/api/cart", json={"product_id": catalog["earbuds"], "quantity": 2}, headers=h)
    cart = client.post("/api/cart", json={"product_id": catalog["kettle"]}, headers=h).json()["id"]
    co = client.post("/api/orders/razorpay/create", json={"cart_id": cart, "address_id": addr}, headers=h).json()
    sig = hmac.new(b"s3cret", f"{co['razorpay_order_id']}|pay_1".encode(), hashlib.sha256).hexdigest()
    client.post("/api/orders/razorpay/verify", headers=h, json={
        "razorpay_order_id": co["razorpay_order_id"], "razorpay_payment_id": "pay_1", "razorpay_signature": sig})
    return {"buyer": h, "order_id": co["order_id"]}


def test_seller_sees_items_with_shipping_address(client, seller, paid_order):
    items = client.get("/api/seller/orders", headers=seller).json()
    assert sorted(i["name"] for i in items) == ["Electric Kettle", "Wireless Earbuds"]
    assert items[0]["ship_address"].startswith("1 Road") and items[0]["next_statuses"] == ["packed", "cancelled"]


def test_status_moves_forward_only_and_buyer_sees_progress(client, seller, paid_order):
    items = client.get("/api/seller/orders", headers=seller).json()
    for item in items:
        for s in ["packed", "shipped"]:
            assert client.patch(f"/api/seller/orders/items/{item['id']}/status", json={"status": s}, headers=seller).status_code == 200
    first = items[0]["id"]
    assert client.patch(f"/api/seller/orders/items/{first}/status", json={"status": "packed"}, headers=seller).status_code == 409
    assert client.patch(f"/api/seller/orders/items/{first}/status", json={"status": "cancelled"}, headers=seller).status_code == 409
    client.patch(f"/api/seller/orders/items/{first}/status", json={"status": "delivered"}, headers=seller)
    order = client.get(f"/api/orders/{paid_order['order_id']}", headers=paid_order["buyer"]).json()
    assert order["progress"] == "shipped"  # one item delivered, the other still on its way
    client.patch(f"/api/seller/orders/items/{items[1]['id']}/status", json={"status": "delivered"}, headers=seller)
    assert client.get(f"/api/orders/{paid_order['order_id']}", headers=paid_order["buyer"]).json()["progress"] == "delivered"
    assert client.get("/api/seller/orders", params={"status_filter": "open"}, headers=seller).json() == []


def test_cancel_before_shipping_restocks(client, seller, paid_order, catalog, db_session):
    item = next(i for i in client.get("/api/seller/orders", headers=seller).json() if i["name"] == "Wireless Earbuds")
    with db_session() as db:
        before = db.get(Product, catalog["earbuds"]).stock
    assert client.patch(f"/api/seller/orders/items/{item['id']}/status", json={"status": "cancelled"}, headers=seller).status_code == 200
    with db_session() as db:
        assert db.get(Product, catalog["earbuds"]).stock == before + 2


def test_other_seller_cannot_update_my_items(client, paid_order, make_user, login):
    make_user(email="other@test.dev", role=Role.seller, seller_status=SellerStatus.approved)
    other = login("other@test.dev")
    assert client.get("/api/seller/orders", headers=other).json() == []
    assert client.patch("/api/seller/orders/items/1/status", json={"status": "packed"}, headers=other).status_code == 404


def test_dashboard_numbers(client, seller, paid_order):
    d = client.get("/api/seller/dashboard", headers=seller).json()
    assert d["revenue"] == 2 * 2499 + 899 and d["orders"] == 1 and d["units_sold"] == 3 and d["to_ship"] == 2
    assert d["live_listings"] == 3 and d["pending_listings"] == 1
    assert d["top_products"][0]["name"] == "Wireless Earbuds" and d["top_products"][0]["units"] == 2
    assert "Mechanical Keyboard" in [p["name"] for p in d["low_stock"]]  # 0 in stock
    listing = next(p for p in client.get("/api/seller/products", headers=seller).json() if p["name"] == "Wireless Earbuds")
    assert listing["units_sold"] == 2


def test_reply_to_review_shows_on_product_page(client, seller, catalog, make_user, login):
    make_user(email="r@test.dev")
    client.post("/api/reviews", json={"product_id": catalog["kettle"], "rating": 2, "body": "Lid is loose"}, headers=login("r@test.dev"))
    review = client.get("/api/seller/reviews", headers=seller).json()[0]
    res = client.post(f"/api/seller/reviews/{review['id']}/response", json={"response": "Sorry! A replacement lid is on its way."}, headers=seller)
    assert res.status_code == 200
    public = client.get(f"/api/reviews/product/{catalog['kettle']}").json()["reviews"][0]
    assert public["seller_response"].startswith("Sorry!")


def test_seller_cannot_reply_to_other_sellers_reviews(client, catalog, make_user, login):
    make_user(email="r@test.dev")
    client.post("/api/reviews", json={"product_id": catalog["kettle"], "rating": 2}, headers=login("r@test.dev"))
    make_user(email="other@test.dev", role=Role.seller, seller_status=SellerStatus.approved)
    other = login("other@test.dev")
    assert client.post("/api/seller/reviews/1/response", json={"response": "Not mine"}, headers=other).status_code == 404
