import math
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_optional_user
from app.models import Category, RecentlyViewed, User, WishlistItem, utcnow
from app.schemas_catalog import CategoryOut, ProductCard, ProductDetail, ProductPage
from app.services.catalog import is_visible, search_products

router = APIRouter(prefix="/api", tags=["catalog"])
RECENT_LIMIT = 20


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return [CategoryOut(id=c.id, name=c.name, slug=c.slug) for c in db.scalars(select(Category).order_by(Category.name))]


@router.get("/products", response_model=ProductPage)
def list_products(
    q: str | None = Query(None, max_length=100),
    category: str | None = None,
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    min_rating: float | None = Query(None, ge=0, le=5),
    in_stock: bool = False,
    sort: str = Query("relevance", pattern="^(relevance|newest|price_asc|price_desc|rating|discount)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=48),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, "Minimum price can't be more than maximum price")
    items, total = search_products(
        db, q=q, category=category, min_price=min_price, max_price=max_price, min_rating=min_rating,
        in_stock=in_stock, sort=sort, page=page, page_size=page_size,
    )
    return ProductPage(items=[ProductCard.of(p) for p in items], total=total, page=page,
                       pages=max(1, math.ceil(total / page_size)))


@router.get("/products/{product_id}", response_model=ProductDetail)
def product_detail(product_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    product = is_visible(db, product_id)
    if product is None:
        raise HTTPException(404, "This product isn't available")

    in_wishlist = False
    if user:
        in_wishlist = db.scalar(select(WishlistItem.id).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id)) is not None
        _remember_view(db, user.id, product_id)

    card = ProductCard.of(product)
    return ProductDetail(**card.model_dump(exclude={"discount_pct", "stock_label"}),
                         low_stock_threshold=product.low_stock_threshold,
                         description=product.description, in_wishlist=in_wishlist)


def _remember_view(db: Session, user_id: int, product_id: int) -> None:
    row = db.scalar(select(RecentlyViewed).where(
        RecentlyViewed.user_id == user_id, RecentlyViewed.product_id == product_id))
    if row:
        row.viewed_at = utcnow()
    else:
        db.add(RecentlyViewed(user_id=user_id, product_id=product_id))
    db.flush()
    # Keep only the latest few per user so the table doesn't grow forever.
    stale = db.scalars(
        select(RecentlyViewed).where(RecentlyViewed.user_id == user_id)
        .order_by(RecentlyViewed.viewed_at.desc(), RecentlyViewed.id.desc()).offset(RECENT_LIMIT)
    ).all()
    for old in stale:
        db.delete(old)
    db.commit()
