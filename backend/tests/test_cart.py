import pytest


@pytest.fixture()
def buyer(make_user, login):
    make_user(email="b@test.dev")
    return login("b@test.dev")


def test_first_visit_creates_default_active_cart(client, catalog, buyer):
    cart = client.get("/api/cart", headers=buyer).json()
    assert cart["name"] == "My cart" and cart["is_active"] and cart["lines"] == []
    assert len(client.get("/api/cart/carts", headers=buyer).json()) == 1


def test_add_merges_and_caps_at_stock_and_ten(client, catalog, buyer):
    pid = catalog["earbuds"]  # stock 10 in the fixture
    client.post("/api/cart", json={"product_id": pid, "quantity": 3}, headers=buyer)
    cart = client.post("/api/cart", json={"product_id": pid, "quantity": 9}, headers=buyer).json()
    assert len(cart["lines"]) == 1 and cart["lines"][0]["quantity"] == 10
    again = client.post("/api/cart", json={"product_id": pid}, headers=buyer)
    assert again.status_code == 409


def test_cannot_add_out_of_stock_or_hidden(client, catalog, buyer):
    assert client.post("/api/cart", json={"product_id": catalog["keyboard"]}, headers=buyer).status_code == 409
    assert client.post("/api/cart", json={"product_id": catalog["hidden"]}, headers=buyer).status_code == 404


def test_totals_and_shipping(client, catalog, buyer):
    cart = client.post("/api/cart", json={"product_id": catalog["kettle"]}, headers=buyer).json()
    assert cart["subtotal"] == 899 and cart["shipping_fee"] == 0 and cart["total"] == 899  # free over ₹499


def test_named_carts_create_activate_rename_delete(client, catalog, buyer):
    client.get("/api/cart", headers=buyer)
    gifts = client.post("/api/cart/carts", json={"name": "Diwali gifts"}, headers=buyer).json()
    assert gifts["is_active"]
    client.post("/api/cart", json={"product_id": catalog["kettle"]}, headers=buyer)
    carts = {c["name"]: c for c in client.get("/api/cart/carts", headers=buyer).json()}
    assert carts["Diwali gifts"]["item_count"] == 1 and carts["My cart"]["item_count"] == 0
    assert client.post("/api/cart/carts", json={"name": "Diwali gifts"}, headers=buyer).status_code == 409
    renamed = client.patch(f"/api/cart/carts/{gifts['id']}", json={"name": "Gifts"}, headers=buyer).json()
    assert renamed["name"] == "Gifts"
    assert client.delete(f"/api/cart/carts/{gifts['id']}", headers=buyer).status_code == 204
    remaining = client.get("/api/cart/carts", headers=buyer).json()
    assert [c["name"] for c in remaining] == ["My cart"] and remaining[0]["is_active"]


def test_move_item_between_carts_merges(client, catalog, buyer):
    home = client.get("/api/cart", headers=buyer).json()
    item = client.post("/api/cart", json={"product_id": catalog["kettle"], "quantity": 2}, headers=buyer).json()["lines"][0]
    other = client.post("/api/cart/carts", json={"name": "Office", "activate": False}, headers=buyer).json()
    client.post("/api/cart", json={"product_id": catalog["kettle"], "cart_id": other["id"]}, headers=buyer)
    left = client.patch(f"/api/cart/{item['id']}", json={"cart_id": other["id"]}, headers=buyer).json()
    assert left["id"] == home["id"] and left["lines"] == []
    office = client.get("/api/cart", params={"cart_id": other["id"]}, headers=buyer).json()
    assert office["lines"][0]["quantity"] == 3


def test_quantity_update_and_remove(client, catalog, buyer):
    line = client.post("/api/cart", json={"product_id": catalog["kettle"]}, headers=buyer).json()["lines"][0]
    assert client.patch(f"/api/cart/{line['id']}", json={"quantity": 99}, headers=buyer).status_code == 422
    assert client.patch(f"/api/cart/{line['id']}", json={"quantity": 4}, headers=buyer).json()["lines"][0]["quantity"] == 4
    assert client.patch(f"/api/cart/{line['id']}", json={"quantity": 0}, headers=buyer).json()["lines"] == []


def test_other_users_carts_are_invisible(client, catalog, buyer, make_user, login):
    mine = client.get("/api/cart", headers=buyer).json()
    make_user(email="other@test.dev")
    other = login("other@test.dev")
    assert client.get("/api/cart", params={"cart_id": mine["id"]}, headers=other).status_code == 404
    assert client.delete(f"/api/cart/carts/{mine['id']}", headers=other).status_code == 404


def test_sellers_cannot_use_carts(client, catalog, login):
    assert client.get("/api/cart", headers=login("good@test.dev")).status_code == 403


ADDRESS = {"full_name": "Hardik A", "phone": "+91 98765 43210", "line1": "12 Mall Road",
           "city": "Karnal", "state": "Haryana", "pincode": "132001"}


def test_addresses_validate_and_first_is_default(client, buyer):
    a = client.post("/api/account/addresses", json=ADDRESS, headers=buyer).json()
    assert a["is_default"] and a["phone"] == "9876543210"
    b = client.post("/api/account/addresses", json={**ADDRESS, "line1": "Other"}, headers=buyer).json()
    assert not b["is_default"]
    assert client.post("/api/account/addresses", json={**ADDRESS, "pincode": "12345"}, headers=buyer).status_code == 422
    assert client.post("/api/account/addresses", json={**ADDRESS, "phone": "12345"}, headers=buyer).status_code == 422
    client.delete(f"/api/account/addresses/{a['id']}", headers=buyer)
    assert client.get("/api/account/addresses", headers=buyer).json()[0]["is_default"] is True
