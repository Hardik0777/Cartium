from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import RecentlyViewed, User, WishlistItem
from app.schemas_catalog import ProductCard, WishlistIn
from app.services.catalog import is_visible

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/wishlist", response_model=list[ProductCard])
def wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(WishlistItem).where(WishlistItem.user_id == user.id)
                      .order_by(WishlistItem.created_at.desc(), WishlistItem.id.desc())).all()
    # Hide products that were removed or whose seller was suspended since they were saved.
    return [ProductCard.of(r.product) for r in rows if is_visible(db, r.product_id)]


@router.post("/wishlist", response_model=ProductCard)
def add_to_wishlist(body: WishlistIn, response: Response,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = is_visible(db, body.product_id)
    if product is None:
        raise HTTPException(404, "This product isn't available")
    exists = db.scalar(select(WishlistItem).where(
        WishlistItem.user_id == user.id, WishlistItem.product_id == body.product_id))
    if not exists:  # adding twice is harmless
        db.add(WishlistItem(user_id=user.id, product_id=body.product_id))
        db.commit()
        response.status_code = status.HTTP_201_CREATED
    return ProductCard.of(product)


@router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_wishlist(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(WishlistItem).where(
        WishlistItem.user_id == user.id, WishlistItem.product_id == product_id))
    if item:
        db.delete(item)
        db.commit()


@router.get("/recently-viewed", response_model=list[ProductCard])
def recently_viewed(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(RecentlyViewed).where(RecentlyViewed.user_id == user.id)
                      .order_by(RecentlyViewed.viewed_at.desc(), RecentlyViewed.id.desc())).all()
    return [ProductCard.of(r.product) for r in rows if is_visible(db, r.product_id)]
