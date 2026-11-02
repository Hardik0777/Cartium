from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, Review


def refresh_rating(db: Session, product_id: int) -> None:
    """Recomputes a product's cached average rating and review count."""
    avg, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id)
    ).one()
    product = db.get(Product, product_id)
    product.rating_count = count
    product.rating_avg = Decimal(str(avg or 0)).quantize(Decimal("0.01"), ROUND_HALF_UP)
