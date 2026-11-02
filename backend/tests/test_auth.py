
SIGNUP = {"name": "Hardik", "email": "Hardik@Example.com", "password": "secret123", "role": "buyer"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


def test_signup_returns_token_and_lowercases_email(client):
    res = client.post("/api/auth/signup", json=SIGNUP)
    assert res.status_code == 201
    body = res.json()
    assert body["access_token"] and body["user"]["email"] == "hardik@example.com"
    assert body["user"]["role"] == "buyer" and body["user"]["seller_status"] is None
    assert "password" not in str(body["user"])


def test_duplicate_email_rejected_case_insensitively(client):
    client.post("/api/auth/signup", json=SIGNUP)
    res = client.post("/api/auth/signup", json={**SIGNUP, "email": "HARDIK@example.com"})
    assert res.status_code == 409


def test_seller_signup_starts_pending(client):
    res = client.post("/api/auth/signup", json={**SIGNUP, "role": "seller"})
    assert res.json()["user"]["seller_status"] == "pending"


def test_cannot_self_register_as_admin(client):
    assert client.post("/api/auth/signup", json={**SIGNUP, "role": "admin"}).status_code == 422


def test_weak_password_rejected(client):
    for bad in ["short1", "lettersonly", "12345678", "a1" * 40]:
        assert client.post("/api/auth/signup", json={**SIGNUP, "password": bad}).status_code == 422, bad


def test_login_and_me(client, make_user, login):
    make_user(email="buyer@test.dev")
    headers = login("buyer@test.dev")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == "buyer@test.dev"


def test_wrong_password_and_unknown_email_get_same_error(client, make_user):
    make_user(email="buyer@test.dev")
    wrong = client.post("/api/auth/login", json={"email": "buyer@test.dev", "password": "nope12345"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@test.dev", "password": "nope12345"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_logout_invalidates_old_token(client, make_user, login):
    make_user(email="buyer@test.dev")
    headers = login("buyer@test.dev")
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/auth/me", headers=login("buyer@test.dev")).status_code == 200


def test_deactivated_user_cannot_log_in(client, make_user):
    make_user(email="banned@test.dev", is_active=False)
    res = client.post("/api/auth/login", json={"email": "banned@test.dev", "password": "Passw0rd!"})
    assert res.status_code == 403
