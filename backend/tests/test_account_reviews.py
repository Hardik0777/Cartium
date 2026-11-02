from app.models import Role, SellerStatus


def test_wishlist_add_is_idempotent_and_removable(client, catalog, make_user, login):
    make_user(email="b@test.dev")
    h = login("b@test.dev")
    pid = catalog["earbuds"]
    assert client.post("/api/account/wishlist", json={"product_id": pid}, headers=h).status_code == 201
    assert client.post("/api/account/wishlist", json={"product_id": pid}, headers=h).status_code == 200
    assert [p["id"] for p in client.get("/api/account/wishlist", headers=h).json()] == [pid]
    assert client.get(f"/api/products/{pid}", headers=h).json()["in_wishlist"] is True
    assert client.delete(f"/api/account/wishlist/{pid}", headers=h).status_code == 204
    assert client.get("/api/account/wishlist", headers=h).json() == []


def test_cannot_wishlist_hidden_product(client, catalog, make_user, login):
    make_user(email="b@test.dev")
    res = client.post("/api/account/wishlist", json={"product_id": catalog["hidden"]}, headers=login("b@test.dev"))
    assert res.status_code == 404


def test_wishlist_requires_login(client, catalog):
    assert client.get("/api/account/wishlist").status_code == 401


def test_recently_viewed_newest_first_without_duplicates(client, catalog, make_user, login):
    make_user(email="b@test.dev")
    h = login("b@test.dev")
    for key in ["earbuds", "kettle", "earbuds"]:
        client.get(f"/api/products/{catalog[key]}", headers=h)
    ids = [p["id"] for p in client.get("/api/account/recently-viewed", headers=h).json()]
    assert ids == [catalog["earbuds"], catalog["kettle"]]


def test_visitors_can_view_products_without_tracking(client, catalog):
    assert client.get(f"/api/products/{catalog['earbuds']}").json()["in_wishlist"] is False


def test_review_updates_rating_and_second_post_edits(client, catalog, make_user, login):
    make_user(email="b1@test.dev")
    make_user(email="b2@test.dev")
    pid = catalog["earbuds"]
    client.post("/api/reviews", json={"product_id": pid, "rating": 5, "body": "Great"}, headers=login("b1@test.dev"))
    client.post("/api/reviews", json={"product_id": pid, "rating": 2}, headers=login("b2@test.dev"))
    client.post("/api/reviews", json={"product_id": pid, "rating": 4, "body": "Edited"}, headers=login("b2@test.dev"))
    summary = client.get(f"/api/reviews/product/{pid}").json()
    assert summary["count"] == 2 and summary["average"] == 4.5
    assert summary["distribution"] == {"5": 1, "4": 1, "3": 0, "2": 0, "1": 0}
    card = client.get(f"/api/products/{pid}").json()
    assert card["rating_avg"] == 4.5 and card["rating_count"] == 2


def test_review_author_shows_first_name_only(client, catalog, make_user, login):
    make_user(email="b@test.dev")  # name "Test User"
    h = login("b@test.dev")
    client.post("/api/reviews", json={"product_id": catalog["kettle"], "rating": 4}, headers=h)
    review = client.get(f"/api/reviews/product/{catalog['kettle']}", headers=h).json()["reviews"][0]
    assert review["author"] == "Test" and review["is_mine"] is True


def test_only_buyers_can_review_and_rating_is_validated(client, catalog, make_user, login):
    make_user(email="s@test.dev", role=Role.seller, seller_status=SellerStatus.approved)
    make_user(email="b@test.dev")
    pid = catalog["earbuds"]
    assert client.post("/api/reviews", json={"product_id": pid, "rating": 5}, headers=login("s@test.dev")).status_code == 403
    assert client.post("/api/reviews", json={"product_id": pid, "rating": 6}, headers=login("b@test.dev")).status_code == 422


def test_deleting_review_recalculates_rating(client, catalog, make_user, login):
    make_user(email="b@test.dev")
    h = login("b@test.dev")
    review = client.post("/api/reviews", json={"product_id": catalog["kettle"], "rating": 3}, headers=h).json()
    assert client.delete(f"/api/reviews/{review['id']}", headers=h).status_code == 204
    assert client.get(f"/api/products/{catalog['kettle']}").json()["rating_count"] == 0
