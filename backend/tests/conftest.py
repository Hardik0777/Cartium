"""Each test gets a fresh database. Uses TEST_DATABASE_URL if set (CI runs this on real MySQL),
otherwise a throwaway SQLite file."""
import os

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.database import Base, create_database_if_missing, get_db, make_engine
from app.main import app
from app.models import Category, ListingStatus, Product, Role, SellerStatus, User


@pytest.fixture()
def db_session(tmp_path):
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    create_database_if_missing(url)
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    def _make(email="user@test.dev", password="Passw0rd!", role=Role.buyer, **extra):
        with db_session() as db:
            user = User(name="Test User", email=email, password_hash=hash_password(password), role=role, **extra)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
    return _make


@pytest.fixture()
def login(client):
    def _login(email, password="Passw0rd!"):
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}
    return _login


@pytest.fixture()
def catalog(db_session):
    """Two categories, an approved seller with 4 products (one out of stock, one pending review),
    and a suspended seller whose product must never be shown."""
    from decimal import Decimal

    with db_session() as db:
        good = User(name="Good Seller", email="good@test.dev", password_hash=hash_password("Passw0rd!"),
                    role=Role.seller, seller_status=SellerStatus.approved)
        bad = User(name="Suspended Seller", email="bad@test.dev", password_hash=hash_password("Passw0rd!"),
                   role=Role.seller, seller_status=SellerStatus.suspended)
        elec, home = Category(name="Electronics", slug="electronics"), Category(name="Home", slug="home")
        db.add_all([good, bad, elec, home])
        db.flush()

        def product(name, cat, price, mrp, stock=10, seller=good, status=ListingStatus.approved, brand="Acme"):
            p = Product(seller_id=seller.id, category_id=cat.id, name=name, brand=brand, description=f"{name} details",
                        price=Decimal(price), mrp=Decimal(mrp), stock=stock, status=status)
            db.add(p)
            return p

        items = {
            "earbuds": product("Wireless Earbuds", elec, 2499, 4999),
            "keyboard": product("Mechanical Keyboard", elec, 4499, 5999, stock=0, brand="KeyNest"),
            "kettle": product("Electric Kettle", home, 899, 1599),
            "pending": product("Unreviewed Gadget", elec, 999, 999, status=ListingStatus.pending),
            "hidden": product("Suspended Seller Lamp", home, 500, 800, seller=bad),
        }
        db.commit()
        return {k: v.id for k, v in items.items()}
