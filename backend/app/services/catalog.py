"""Catalog queries. Only listings an admin approved, from active approved sellers, are visible to shoppers."""
from decimal import Decimal

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Category, ListingStatus, Product, SellerStatus, User

SORTS = {
    "newest": [Product.created_at.desc(), Product.id.desc()],
    "price_asc": [Product.price.asc(), Product.id.asc()],
    "price_desc": [Product.price.desc(), Product.id.desc()],
    "rating": [Product.rating_avg.desc(), Product.rating_count.desc(), Product.id.desc()],
    "discount": [((Product.mrp - Product.price) / Product.mrp).desc(), Product.id.desc()],
}


def visible_products() -> Select:
    return (
        select(Product)
        .join(User, Product.seller_id == User.id)
        .where(
            Product.status == ListingStatus.approved,
            User.is_active.is_(True),
            User.seller_status == SellerStatus.approved,
        )
    )


def is_visible(db: Session, product_id: int) -> Product | None:
    return db.scalar(visible_products().where(Product.id == product_id))


def search_products(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
    sort: str = "relevance",
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[Product], int]:
    query = visible_products()
    if q:
        # Escape LIKE wildcards so a search for "100%" doesn't match everything.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        query = query.where(or_(
            Product.name.ilike(like, escape="\\"),
            Product.brand.ilike(like, escape="\\"),
            Product.description.ilike(like, escape="\\"),
        ))
    if category:
        query = query.join(Category, Product.category_id == Category.id).where(Category.slug == category)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if min_rating:
        query = query.where(Product.rating_avg >= min_rating)
    if in_stock:
        query = query.where(Product.stock > 0)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))

    if sort == "relevance" and q:
        term = q.strip()
        # Name matches first, then brand, then description; ties broken by rating.
        rank = case(
            (Product.name.ilike(f"{term}%"), 0),
            (Product.name.ilike(f"%{term}%"), 1),
            (Product.brand.ilike(f"%{term}%"), 2),
            else_=3,
        )
        order = [rank, Product.rating_avg.desc(), Product.id.desc()]
    else:
        order = SORTS.get(sort, SORTS["newest"])

    items = list(db.scalars(query.order_by(*order).offset((page - 1) * page_size).limit(page_size)).unique())
    return items, total
