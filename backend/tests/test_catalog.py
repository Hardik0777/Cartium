def names(res):
    return [p["name"] for p in res.json()["items"]]


def test_only_approved_listings_from_approved_sellers_are_listed(client, catalog):
    res = client.get("/api/products")
    assert res.json()["total"] == 3
    assert set(names(res)) == {"Wireless Earbuds", "Mechanical Keyboard", "Electric Kettle"}


def test_hidden_products_return_404(client, catalog):
    assert client.get(f"/api/products/{catalog['pending']}").status_code == 404
    assert client.get(f"/api/products/{catalog['hidden']}").status_code == 404
    assert client.get("/api/products/999999").status_code == 404


def test_search_matches_name_brand_and_ranks_name_first(client, catalog):
    assert names(client.get("/api/products", params={"q": "keyboard"})) == ["Mechanical Keyboard"]
    assert names(client.get("/api/products", params={"q": "keynest"})) == ["Mechanical Keyboard"]
    assert client.get("/api/products", params={"q": "zzz"}).json()["total"] == 0


def test_search_treats_wildcards_literally(client, catalog):
    assert client.get("/api/products", params={"q": "%"}).json()["total"] == 0


def test_filters_and_sorting(client, catalog):
    assert names(client.get("/api/products", params={"category": "home"})) == ["Electric Kettle"]
    cheap = client.get("/api/products", params={"max_price": 1000})
    assert names(cheap) == ["Electric Kettle"]
    assert "Mechanical Keyboard" not in names(client.get("/api/products", params={"in_stock": True}))
    assert names(client.get("/api/products", params={"sort": "price_asc"}))[0] == "Electric Kettle"
    assert names(client.get("/api/products", params={"sort": "price_desc"}))[0] == "Mechanical Keyboard"
    assert client.get("/api/products", params={"min_price": 900, "max_price": 100}).status_code == 422


def test_pagination(client, catalog):
    page1 = client.get("/api/products", params={"page_size": 2, "sort": "price_asc"}).json()
    page2 = client.get("/api/products", params={"page_size": 2, "page": 2, "sort": "price_asc"}).json()
    assert page1["pages"] == 2 and len(page1["items"]) == 2 and len(page2["items"]) == 1
    assert not {p["id"] for p in page1["items"]} & {p["id"] for p in page2["items"]}


def test_card_has_discount_and_stock_labels(client, catalog):
    cards = {p["name"]: p for p in client.get("/api/products").json()["items"]}
    assert cards["Wireless Earbuds"]["discount_pct"] == 50
    assert cards["Mechanical Keyboard"]["stock_label"] == "out_of_stock"
    assert isinstance(cards["Electric Kettle"]["price"], (int, float))


def test_categories(client, catalog):
    assert [c["slug"] for c in client.get("/api/categories").json()] == ["electronics", "home"]
