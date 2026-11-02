import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# MySQL's DATETIME keeps whole seconds by default, so two events in the same second would tie
# (e.g. "recently viewed" order). fsp=6 keeps microseconds; other databases use the plain type.
Timestamp = DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), "mysql", "mariadb")


class Role(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    admin = "admin"


class SellerStatus(str, enum.Enum):
    pending = "pending"      # signed up, waiting for admin approval
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Null for accounts that only sign in with Google (added in Phase 6).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20), default=Role.buyer)
    seller_status: Mapped[SellerStatus | None] = mapped_column(
        Enum(SellerStatus, native_enum=False, length=20), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bumped on logout; tokens carrying an older version stop working.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)


# ---------------------------------------------------------------- catalog (Phase 2)


class ListingStatus(str, enum.Enum):
    pending = "pending"      # waiting for admin review (Phase 5)
    approved = "approved"    # visible in the store
    rejected = "rejected"
    removed = "removed"      # taken down by an admin


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    brand: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # Money is stored as exact decimals, never floats: 0.1 + 0.2 must equal 0.3 on an invoice.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, native_enum=False, length=20), default=ListingStatus.pending, index=True
    )
    # Kept up to date whenever a review changes, so listing pages don't re-average every request.
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow, index=True)

    seller: Mapped[User] = relationship(lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)

    product: Mapped[Product] = relationship(lazy="joined")


class RecentlyViewed(Base):
    __tablename__ = "recently_viewed"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    viewed_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)

    product: Mapped[Product] = relationship(lazy="joined")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)  # one review per buyer per product

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[str] = mapped_column(Text, default="")
    seller_response: Mapped[str | None] = mapped_column(Text, nullable=True)  # Phase 4
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(lazy="joined")
