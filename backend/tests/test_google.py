"""Google sign-in. Tokens are signed with a test RSA key in exactly Google's format, and the real
verification code checks them (only the download of Google's public keys is replaced)."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.models import Role
from app.services import google

CLIENT_ID = "1234-test.apps.googleusercontent.com"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": KEY.public_key()})()


@pytest.fixture(autouse=True)
def google_setup(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google, "_jwks_client", lambda url: FakeJWKS())


def token(sub="g-123", email="asha@gmail.com", name="Asha Verma", aud=CLIENT_ID, iss="https://accounts.google.com",
          verified=True, exp_in=3600, key=KEY):
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "sub": sub, "email": email, "email_verified": verified, "name": name,
              "iat": now, "exp": now + exp_in}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def test_first_sign_in_asks_for_role_then_creates_account(client):
    first = client.post("/api/auth/oauth", json={"credential": token()})
    assert first.status_code == 200 and first.json() == {"needs_role": True, "name": "Asha Verma", "email": "asha@gmail.com"}
    second = client.post("/api/auth/oauth", json={"credential": token(), "role": "seller"}).json()
    assert second["user"]["role"] == "seller" and second["user"]["seller_status"] == "pending"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}).json()
    assert me["email"] == "asha@gmail.com"


def test_returning_user_signs_straight_in_even_if_email_changed(client):
    client.post("/api/auth/oauth", json={"credential": token(), "role": "buyer"})
    again = client.post("/api/auth/oauth", json={"credential": token(email="asha.new@gmail.com")}).json()
    assert again["user"]["email"] == "asha@gmail.com"  # matched on Google's stable id, not email


def test_links_to_existing_password_account_with_same_email(client, make_user):
    make_user(email="asha@gmail.com", role=Role.seller)
    res = client.post("/api/auth/oauth", json={"credential": token()}).json()
    assert res["user"]["role"] == "seller"  # no role prompt; their existing account is used
    assert client.post("/api/auth/login", json={"email": "asha@gmail.com", "password": "Passw0rd!"}).status_code == 200


def test_google_only_account_has_no_password_login(client):
    client.post("/api/auth/oauth", json={"credential": token(), "role": "buyer"})
    res = client.post("/api/auth/login", json={"email": "asha@gmail.com", "password": "anything123"})
    assert res.status_code == 401


@pytest.mark.parametrize("bad", [
    {"aud": "someone-elses-app.apps.googleusercontent.com"},
    {"iss": "https://evil.example.com"},
    {"exp_in": -3600},
    {"key": OTHER_KEY},
    {"verified": False},
])
def test_rejects_bad_tokens(client, bad):
    res = client.post("/api/auth/oauth", json={"credential": token(**bad), "role": "buyer"})
    assert res.status_code == 401


def test_cannot_pick_admin(client):
    assert client.post("/api/auth/oauth", json={"credential": token(), "role": "admin"}).status_code == 422


def test_banned_user_stays_out(client, make_user):
    make_user(email="asha@gmail.com", is_active=False)
    assert client.post("/api/auth/oauth", json={"credential": token()}).status_code == 403


def test_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.post("/api/auth/oauth", json={"credential": token()}).status_code == 503
    assert client.get("/api/auth/config").json() == {"google_client_id": None}
