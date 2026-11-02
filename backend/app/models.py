import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
