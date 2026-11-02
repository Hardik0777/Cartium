import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas_catalog import ProductCard


# ---------------------------------------------------------------- carts
class CartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    activate: bool = True

    @field_validator("name")
    @classmethod
    def clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the cart a name")
        return v


class CartRename(CartCreate):
    activate: bool = False


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=10)
    cart_id: int | None = None  # defaults to the active cart


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=10)  # 0 removes the item
    cart_id: int | None = None                               # move the item to another cart


class CartLine(BaseModel):
    id: int
    product: ProductCard
    quantity: int
    line_total: float
    problem: str | None  # why this line can't be checked out right now, if anything


class CartSummary(BaseModel):
    id: int
    name: str
    is_active: bool
    item_count: int
    subtotal: float


class CartDetail(CartSummary):
    lines: list[CartLine]
    shipping_fee: float
    total: float
    can_checkout: bool


# ---------------------------------------------------------------- addresses
class AddressIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str
    line1: str = Field(min_length=3, max_length=200)
    line2: str = Field(default="", max_length=200)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    pincode: str
    is_default: bool = False

    @field_validator("phone")
    @classmethod
    def indian_mobile(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ValueError("Enter a 10-digit Indian mobile number")
        return digits

    @field_validator("pincode")
    @classmethod
    def pin(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[1-9]\d{5}", v):
            raise ValueError("Enter a valid 6-digit PIN code")
        return v


class AddressOut(AddressIn):
    id: int


# ---------------------------------------------------------------- orders
class CheckoutIn(BaseModel):
    cart_id: int
    address_id: int


class CheckoutOut(BaseModel):
    order_id: int
    razorpay_order_id: str
    amount: int          # in paise, as Razorpay expects
    currency: str
    key_id: str
    name: str
    email: str
    contact: str


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    name: str
    unit_price: float
    quantity: int
    status: str
    status_updated_at: datetime
    seller_name: str


class OrderOut(BaseModel):
    id: int
    cart_name: str
    status: str
    progress: str        # overall delivery progress shown to the buyer
    subtotal: float
    shipping_fee: float
    total: float
    ship_name: str
    ship_phone: str
    ship_address: str
    created_at: datetime
    paid_at: datetime | None
    items: list[OrderItemOut]


class ReorderOut(BaseModel):
    cart_id: int
    added: list[str]
    skipped: list[str]
