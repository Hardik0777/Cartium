from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserRow(BaseModel):
    id: int
    name: str
    email: str
    role: str
    seller_status: str | None
    is_active: bool
    created_at: datetime
    orders: int
    listings: int


class UserUpdate(BaseModel):
    is_active: bool | None = None
    role: Literal["buyer", "seller", "admin"] | None = None
    seller_status: Literal["pending", "approved", "rejected", "suspended"] | None = None
    note: str = Field(default="", max_length=500)


class ModerationIn(BaseModel):
    status: Literal["approved", "rejected", "removed"]
    note: str = Field(default="", max_length=500)

    @field_validator("note")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ProductRow(BaseModel):
    id: int
    name: str
    brand: str
    description: str
    category: str
    price: float
    mrp: float
    stock: int
    image_url: str | None
    status: str
    seller_id: int
    seller_name: str
    created_at: datetime


class RefundRow(BaseModel):
    id: int
    order_id: int
    buyer_name: str
    buyer_email: str
    amount: float
    reason: str
    status: str
    razorpay_payment_id: str | None
    razorpay_refund_id: str | None
    created_at: datetime
    processed_at: datetime | None


class RefundDecision(BaseModel):
    action: Literal["process", "reject"]
    note: str = Field(default="", max_length=500)


class ComplaintIn(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=3000)


class ComplaintRow(BaseModel):
    id: int
    order_id: int
    buyer_name: str
    subject: str
    message: str
    status: str
    admin_reply: str | None
    created_at: datetime
    resolved_at: datetime | None


class ComplaintDecision(BaseModel):
    reply: str = Field(min_length=2, max_length=2000)


class Flag(BaseModel):
    kind: str          # high_value_order | abandoned_checkouts | seller_cancellations
    severity: Literal["review", "high"]
    message: str
    user_id: int | None = None
    order_id: int | None = None


class DayPoint(BaseModel):
    day: str
    orders: int
    revenue: float


class AuditRow(BaseModel):
    id: int
    admin_name: str
    target_type: str
    target_id: int
    action: str
    note: str
    created_at: datetime


class AdminDashboard(BaseModel):
    buyers: int
    sellers: int
    new_users_7d: int
    paid_orders: int
    gmv: float
    gmv_30d: float
    pending_sellers: int
    pending_listings: int
    refunds_requested: int
    open_complaints: int
    last_14_days: list[DayPoint]
    flags: list[Flag]
    recent_actions: list[AuditRow]
