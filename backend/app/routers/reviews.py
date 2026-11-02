from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_optional_user, require_role
from app.models import Review, Role, User
from app.schemas_catalog import ReviewIn, ReviewOut, ReviewSummary
from app.services.catalog import is_visible
from app.services.reviews import refresh_rating

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _out(r: Review, viewer: User | None) -> ReviewOut:
    return ReviewOut(id=r.id, rating=r.rating, body=r.body, author=r.user.name.split()[0],
                     is_mine=viewer is not None and viewer.id == r.user_id,
                     seller_response=r.seller_response, created_at=r.created_at)


@router.get("/product/{product_id}", response_model=ReviewSummary)
def product_reviews(product_id: int, db: Session = Depends(get_db), viewer: User | None = Depends(get_optional_user)):
    product = is_visible(db, product_id)
    if product is None:
        raise HTTPException(404, "This product isn't available")
    reviews = db.scalars(select(Review).where(Review.product_id == product_id)
                         .order_by(Review.updated_at.desc(), Review.id.desc())).all()
    distribution = {stars: 0 for stars in range(5, 0, -1)}
    for r in reviews:
        distribution[r.rating] += 1
    return ReviewSummary(average=float(product.rating_avg), count=product.rating_count,
                         distribution=distribution, reviews=[_out(r, viewer) for r in reviews])


@router.post("", response_model=ReviewOut)
def upsert_review(body: ReviewIn, user: User = Depends(require_role(Role.buyer)), db: Session = Depends(get_db)):
    """Creates the buyer's review, or updates it if they already reviewed this product."""
    if is_visible(db, body.product_id) is None:
        raise HTTPException(404, "This product isn't available")
    review = db.scalar(select(Review).where(Review.user_id == user.id, Review.product_id == body.product_id))
    if review:
        review.rating, review.body = body.rating, body.body
    else:
        review = Review(user_id=user.id, product_id=body.product_id, rating=body.rating, body=body.body)
        db.add(review)
    db.flush()
    refresh_rating(db, body.product_id)
    db.commit()
    db.refresh(review)
    return _out(review, user)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, user: User = Depends(require_role(Role.buyer)), db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if review is None or review.user_id != user.id:
        raise HTTPException(404, "Review not found")
    product_id = review.product_id
    db.delete(review)
    db.flush()
    refresh_rating(db, product_id)
    db.commit()
