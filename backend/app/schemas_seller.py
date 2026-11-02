from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ListingIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    brand: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)
    category_id: int
    price: float = Field(gt=0, le=10_000_000)
    mrp: float = Field(gt=0, le=10_000_000)
    stock: int = Field(ge=0, le=100_000)
    low_stock_threshold: int = Field(default=5, ge=0, le=1000)
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("name", "brand", "description")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("image_url")
    @classmethod
    def safe_image(cls, v: str | None) -> str | None:
        # Only our own uploads or https links, so a listing can't point at javascript: or http: content.
        if v and not (v.startswith("/uploads/") or v.startswith("https://")):
            raise ValueError("Image must be an uploaded photo or an https link")
        return v or None

    @model_validator(mode="after")
    def price_not_above_mrp(self):
        if self.price > self.mrp:
            raise ValueError("Selling price can't be higher than MRP")
        return self


class ListingOut(BaseModel):
    id: int
    name: str
    brand: str
    description: str
    category_id: int
    category_name: str
    category_slug: str
    price: float
    mrp: float
    stock: int
    low_stock_threshold: int
    image_url: str | None
    status: str
    rating_avg: float
    rating_count: int
    units_sold: int
    created_at: datetime


class SellerOrderItem(BaseModel):
    id: int
    order_id: int
    product_id: int | None
    name: str
    quantity: int
    unit_price: float
    status: str
    status_updated_at: datetime
    ordered_at: datetime
    buyer_name: str
    ship_name: str
    ship_phone: str
    ship_address: str
    next_statuses: list[str]


class ItemStatusIn(BaseModel):
    status: Literal["packed", "shipped", "delivered", "cancelled"]


class TopProduct(BaseModel):
    id: int
    name: str
    units: int
    revenue: float


class Dashboard(BaseModel):
    revenue: float
    orders: int
    units_sold: int
    to_ship: int
    live_listings: int
    pending_listings: int
    average_rating: float | None
    low_stock: list[ListingOut]
    top_products: list[TopProduct]


class SellerReview(BaseModel):
    id: int
    product_id: int
    product_name: str
    rating: int
    body: str
    author: str
    seller_response: str | None
    created_at: datetime


class ResponseIn(BaseModel):
    response: str = Field(min_length=2, max_length=1000)

    @field_validator("response")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()
