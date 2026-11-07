"""Creates the database and tables, then adds demo accounts.

Run from the backend folder:  python -m app.seed
Safe to run again: existing accounts are left alone.
"""
from decimal import Decimal

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.database import Base, SessionLocal, create_database_if_missing, engine
from app.data.catalog import CATEGORIES, PRODUCTS, REVIEWS
from app.models import Category, ListingStatus, Product, Review, Role, SellerStatus, User

# Demo accounts. On a public deployment the buyer and seller logins stay public so visitors can try
# the site, but the admin password must come from SEED_ADMIN_PASSWORD.
DEMO_USERS = [
    {"name": "Admin User", "email": "admin@cartium.dev", "password": "Admin@123", "role": Role.admin},
    {"name": "Sharma Electronics", "email": "seller@cartium.dev", "password": "Seller@123",
     "role": Role.seller, "seller_status": SellerStatus.approved},
    {"name": "Kala Home Studio", "email": "home@cartium.dev", "password": "Seller@123",
     "role": Role.seller, "seller_status": SellerStatus.approved},
    {"name": "Demo Buyer", "email": "buyer@cartium.dev", "password": "Buyer@123", "role": Role.buyer},
    {"name": "Second Buyer", "email": "buyer2@cartium.dev", "password": "Buyer@123", "role": Role.buyer},
]


def _password(u: dict) -> str:
    if u["role"] == Role.admin and settings.seed_admin_password:
        return settings.seed_admin_password
    if u["role"] == Role.admin and settings.app_env == "production":
        raise SystemExit("Set SEED_ADMIN_PASSWORD before seeding a production database")
    return u["password"]


def seed() -> None:
    create_database_if_missing(settings.database_url)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for u in DEMO_USERS:
            if db.scalar(select(User).where(User.email == u["email"])):
                print(f"  exists   {u['email']}")
                continue
            db.add(User(name=u["name"], email=u["email"], password_hash=hash_password(_password(u)),
                        role=u["role"], seller_status=u.get("seller_status")))
            print(f"  created  {u['email']}  ({u['role'].value})")
        db.commit()
        seed_catalog(db)
        try:
            from app.ai import index
            built = index.rebuild(db)
            print(f"  assistant index: {built['products']} products, {built['faqs']} FAQs, {built['policies']} policies")
        except Exception as exc:  # e.g. offline: it's rebuilt automatically on the first question
            print(f"  assistant index skipped ({type(exc).__name__}); it will build on first use")
    print("Seed complete.")


def seed_catalog(db) -> None:
    for name, slug in CATEGORIES:
        if not db.scalar(select(Category).where(Category.slug == slug)):
            db.add(Category(name=name, slug=slug))
    db.commit()

    if db.scalar(select(func.count(Product.id))):
        print("  products already seeded")
        return
    users = {u.email: u for u in db.scalars(select(User))}
    cats = {c.slug: c for c in db.scalars(select(Category))}
    for seller, cat, name, brand, price, mrp, stock, desc in PRODUCTS:
        db.add(Product(seller_id=users[seller].id, category_id=cats[cat].id, name=name, brand=brand,
                       description=desc, price=Decimal(price), mrp=Decimal(mrp), stock=stock,
                       status=ListingStatus.approved))
    db.commit()

    products = {p.name: p for p in db.scalars(select(Product))}
    for email, product_name, rating, body in REVIEWS:
        db.add(Review(user_id=users[email].id, product_id=products[product_name].id, rating=rating, body=body))
    db.commit()
    from app.services.reviews import refresh_rating  # local import: avoids a cycle at module load
    for product in products.values():
        refresh_rating(db, product.id)
    db.commit()
    print(f"  created  {len(CATEGORIES)} categories, {len(PRODUCTS)} products, {len(REVIEWS)} reviews")


if __name__ == "__main__":
    seed()
