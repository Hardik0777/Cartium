"""Creates the database and tables, then adds demo accounts.

Run from the backend folder:  python -m app.seed
Safe to run again: existing accounts are left alone.
"""
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.database import Base, SessionLocal, create_database_if_missing, engine
from app.models import Role, SellerStatus, User

# Local demo only. Change these before deploying anywhere public.
DEMO_USERS = [
    {"name": "Admin User", "email": "admin@cartium.dev", "password": "Admin@123", "role": Role.admin},
    {"name": "Sharma Electronics", "email": "seller@cartium.dev", "password": "Seller@123",
     "role": Role.seller, "seller_status": SellerStatus.approved},
    {"name": "Demo Buyer", "email": "buyer@cartium.dev", "password": "Buyer@123", "role": Role.buyer},
]


def seed() -> None:
    create_database_if_missing(settings.database_url)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for u in DEMO_USERS:
            if db.scalar(select(User).where(User.email == u["email"])):
                print(f"  exists   {u['email']}")
                continue
            db.add(User(name=u["name"], email=u["email"], password_hash=hash_password(u["password"]),
                        role=u["role"], seller_status=u.get("seller_status")))
            print(f"  created  {u['email']}  ({u['role'].value})")
        db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    seed()
