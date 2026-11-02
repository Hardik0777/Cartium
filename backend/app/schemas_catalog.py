from datetime import datetime

from pydantic import BaseModel, Field, computed_field, field_validator

from app.models import Product


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str


class SellerBrief(BaseModel):
    id: int
    name: str


class ProductCard(BaseModel):
    id: int
    name: str
    brand: str
    price: float
    mrp: float
    stock: int
    image_url: str | None
    rating_avg: float
    rating_count: int
    category: CategoryOut
    seller: SellerBrief
    low_stock_threshold: int = Field(exclude=True)

    @computed_field
    @property
    def discount_pct(self) -> int:
        return round((self.mrp - self.price) / self.mrp * 100) if self.mrp > self.price else 0

    @computed_field
    @property
    def stock_label(self) -> str:
        if self.stock <= 0:
            return "out_of_stock"
        return "low" if self.stock <= self.low_stock_threshold else "in_stock"

    @classmethod
    def of(cls, p: Product) -> "ProductCard":
        return cls(
            id=p.id, name=p.name, brand=p.brand, price=float(p.price), mrp=float(p.mrp), stock=p.stock,
            image_url=p.image_url, rating_avg=float(p.rating_avg), rating_count=p.rating_count,
            low_stock_threshold=p.low_stock_threshold,
            category=CategoryOut(id=p.category.id, name=p.category.name, slug=p.category.slug),
            seller=SellerBrief(id=p.seller.id, name=p.seller.name),
        )


class ProductDetail(ProductCard):
    description: str
    in_wishlist: bool = False


class ProductPage(BaseModel):
    items: list[ProductCard]
    total: int
    page: int
    pages: int


class ReviewIn(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=2000)

    @field_validator("body")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ReviewOut(BaseModel):
    id: int
    rating: int
    body: str
    author: str          # first name only, to protect reviewers' privacy
    is_mine: bool
    seller_response: str | None
    created_at: datetime


class ReviewSummary(BaseModel):
    average: float
    count: int
    distribution: dict[int, int]   # stars -> number of reviews
    reviews: list[ReviewOut]


class WishlistIn(BaseModel):
    product_id: int
