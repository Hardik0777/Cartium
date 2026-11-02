from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_approved_seller
from app.models import (
    AdminAction, Category, ItemStatus, ListingStatus, Order, OrderItem, OrderStatus, Product, Refund, Review, User,
    utcnow,
)
from app.schemas_seller import (
    Dashboard, ItemStatusIn, ListingIn, ListingOut, ResponseIn, SellerOrderItem, SellerReview, TopProduct,
)
from app.services.orders import _aware
from app.services.uploads import save_image

router = APIRouter(prefix="/api/seller", tags=["seller"])
seller = require_approved_seller

# Shipping only moves forward. Cancelling is allowed until the parcel leaves.
NEXT = {
    ItemStatus.placed: [ItemStatus.packed, ItemStatus.cancelled],
    ItemStatus.packed: [ItemStatus.shipped, ItemStatus.cancelled],
    ItemStatus.shipped: [ItemStatus.delivered],
    ItemStatus.delivered: [],
    ItemStatus.cancelled: [],
}
PAID_LIVE = (OrderStatus.paid,)


def _units_sold(db: Session, product_ids: list[int]) -> dict[int, int]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(OrderItem.product_id, func.sum(OrderItem.quantity))
        .join(Order).where(Order.status == OrderStatus.paid, OrderItem.status != ItemStatus.cancelled,
                           OrderItem.product_id.in_(product_ids))
        .group_by(OrderItem.product_id)
    ).all()
    return {pid: int(n) for pid, n in rows}


def _moderation_note(db: Session, product_id: int) -> str | None:
    last = db.scalar(select(AdminAction).where(AdminAction.target_type == "product", AdminAction.target_id == product_id)
                     .order_by(AdminAction.id.desc()))
    return last.note if last and last.action in ("rejected", "removed") and last.note else None


def _listing(p: Product, sold: int = 0, db: Session | None = None) -> ListingOut:
    return ListingOut(moderation_note=_moderation_note(db, p.id) if db is not None and p.status in (ListingStatus.rejected, ListingStatus.removed) else None,id=p.id, name=p.name, brand=p.brand, description=p.description, category_id=p.category_id,
                      category_name=p.category.name, category_slug=p.category.slug, price=float(p.price), mrp=float(p.mrp), stock=p.stock,
                      low_stock_threshold=p.low_stock_threshold, image_url=p.image_url, status=p.status.value,
                      rating_avg=float(p.rating_avg), rating_count=p.rating_count, units_sold=sold,
                      created_at=_aware(p.created_at))


def _own_product(db: Session, user: User, product_id: int) -> Product:
    p = db.get(Product, product_id)
    if p is None or p.seller_id != user.id:
        raise HTTPException(404, "Listing not found")
    return p


def _check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(422, "Choose a valid category")


# ----------------------------------------------------------------- listings
@router.get("/products", response_model=list[ListingOut])
def my_listings(user: User = Depends(seller), db: Session = Depends(get_db)):
    products = db.scalars(select(Product).where(Product.seller_id == user.id).order_by(Product.created_at.desc(), Product.id.desc())).all()
    sold = _units_sold(db, [p.id for p in products])
    return [_listing(p, sold.get(p.id, 0), db) for p in products]


@router.post("/products", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingIn, user: User = Depends(seller), db: Session = Depends(get_db)):
    _check_category(db, body.category_id)
    # New listings stay hidden until an admin approves them (admin tools: Phase 5).
    p = Product(seller_id=user.id, status=ListingStatus.pending, **{
        **body.model_dump(), "price": Decimal(str(body.price)), "mrp": Decimal(str(body.mrp))})
    db.add(p)
    db.commit()
    db.refresh(p)
    return _listing(p)


@router.patch("/products/{product_id}", response_model=ListingOut)
def edit_listing(product_id: int, body: ListingIn, user: User = Depends(seller), db: Session = Depends(get_db)):
    p = _own_product(db, user, product_id)
    if p.status == ListingStatus.removed:
        raise HTTPException(403, "An admin removed this listing, so it can't be edited")
    _check_category(db, body.category_id)
    for k, v in body.model_dump().items():
        setattr(p, k, Decimal(str(v)) if k in ("price", "mrp") else v)
    if p.status == ListingStatus.rejected:
        p.status = ListingStatus.pending  # fixing a rejected listing sends it back for review
    db.commit()
    db.refresh(p)
    return _listing(p, _units_sold(db, [p.id]).get(p.id, 0))


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(product_id: int, user: User = Depends(seller), db: Session = Depends(get_db)):
    p = _own_product(db, user, product_id)
    # Past orders keep their own copy of the name and price, so deleting is safe for order history.
    db.delete(p)
    db.commit()


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_photo(file: UploadFile = File(...), user: User = Depends(seller)):
    return {"url": await save_image(file)}


# ------------------------------------------------------------------- orders
def _seller_item(item: OrderItem, order: Order, buyer: User) -> SellerOrderItem:
    return SellerOrderItem(
        id=item.id, order_id=order.id, product_id=item.product_id, name=item.name, quantity=item.quantity,
        unit_price=float(item.unit_price), status=item.status.value, status_updated_at=_aware(item.status_updated_at),
        ordered_at=_aware(order.paid_at or order.created_at), buyer_name=buyer.name.split()[0],
        ship_name=order.ship_name, ship_phone=order.ship_phone, ship_address=order.ship_address,
        next_statuses=[s.value for s in NEXT[item.status]],
    )


@router.get("/orders", response_model=list[SellerOrderItem])
def my_orders(status_filter: str | None = None, user: User = Depends(seller), db: Session = Depends(get_db)):
    query = (select(OrderItem, Order, User).join(Order, OrderItem.order_id == Order.id).join(User, Order.user_id == User.id)
             .where(OrderItem.seller_id == user.id, Order.status == OrderStatus.paid))
    if status_filter == "open":
        query = query.where(OrderItem.status.in_([ItemStatus.placed, ItemStatus.packed, ItemStatus.shipped]))
    elif status_filter:
        try:
            query = query.where(OrderItem.status == ItemStatus(status_filter))
        except ValueError:
            raise HTTPException(422, "Unknown status filter")
    rows = db.execute(query.order_by(Order.paid_at.desc(), OrderItem.id.desc())).all()
    return [_seller_item(i, o, b) for i, o, b in rows]


@router.patch("/orders/items/{item_id}/status", response_model=SellerOrderItem)
def update_item_status(item_id: int, body: ItemStatusIn, user: User = Depends(seller), db: Session = Depends(get_db)):
    item = db.get(OrderItem, item_id, with_for_update=True, populate_existing=True)
    if item is None or item.seller_id != user.id or item.order.status != OrderStatus.paid:
        raise HTTPException(404, "Order item not found")
    new = ItemStatus(body.status)
    if new not in NEXT[item.status]:
        raise HTTPException(409, f"Can't change an item from {item.status.value} to {new.value}")
    if new == ItemStatus.cancelled and item.product_id:
        product = db.get(Product, item.product_id, with_for_update=True, populate_existing=True)
        if product:
            product.stock += item.quantity  # put it back on the shelf
    if new == ItemStatus.cancelled:
        # The buyer paid for this item, so queue a refund for an admin to send.
        db.add(Refund(order_id=item.order_id, order_item_id=item.id, amount=item.unit_price * item.quantity,
                      reason=f"Seller cancelled: {item.name} × {item.quantity}"))
    item.status = new
    item.status_updated_at = utcnow()
    db.commit()
    return _seller_item(item, item.order, db.get(User, item.order.user_id))


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard", response_model=Dashboard)
def dashboard(user: User = Depends(seller), db: Session = Depends(get_db)):
    sold_items = (select(OrderItem).join(Order)
                  .where(OrderItem.seller_id == user.id, Order.status == OrderStatus.paid,
                         OrderItem.status != ItemStatus.cancelled))
    items = db.scalars(sold_items).all()
    revenue = sum((i.unit_price * i.quantity for i in items), Decimal("0"))

    per_product: dict[int, TopProduct] = {}
    for i in items:
        if i.product_id is None:
            continue
        tp = per_product.setdefault(i.product_id, TopProduct(id=i.product_id, name=i.name, units=0, revenue=0))
        tp.units += i.quantity
        tp.revenue += float(i.unit_price * i.quantity)

    products = db.scalars(select(Product).where(Product.seller_id == user.id)).all()
    rated = [p for p in products if p.rating_count]
    avg = (sum(float(p.rating_avg) * p.rating_count for p in rated) / sum(p.rating_count for p in rated)) if rated else None
    low = [p for p in products if p.status == ListingStatus.approved and p.stock <= p.low_stock_threshold]
    sold = _units_sold(db, [p.id for p in low])

    return Dashboard(
        revenue=float(revenue),
        orders=len({i.order_id for i in items}),
        units_sold=sum(i.quantity for i in items),
        to_ship=sum(1 for i in items if i.status in (ItemStatus.placed, ItemStatus.packed)),
        live_listings=sum(1 for p in products if p.status == ListingStatus.approved),
        pending_listings=sum(1 for p in products if p.status == ListingStatus.pending),
        average_rating=round(avg, 2) if avg is not None else None,
        low_stock=[_listing(p, sold.get(p.id, 0)) for p in sorted(low, key=lambda p: p.stock)],
        top_products=sorted(per_product.values(), key=lambda t: (-t.units, -t.revenue))[:5],
    )


# ------------------------------------------------------------------ reviews
@router.get("/reviews", response_model=list[SellerReview])
def my_reviews(user: User = Depends(seller), db: Session = Depends(get_db)):
    rows = db.execute(select(Review, Product).join(Product).where(Product.seller_id == user.id)
                      .order_by(Review.updated_at.desc(), Review.id.desc())).all()
    return [SellerReview(id=r.id, product_id=p.id, product_name=p.name, rating=r.rating, body=r.body,
                         author=r.user.name.split()[0], seller_response=r.seller_response,
                         created_at=_aware(r.created_at)) for r, p in rows]


@router.post("/reviews/{review_id}/response", response_model=SellerReview)
def respond(review_id: int, body: ResponseIn, user: User = Depends(seller), db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    product = db.get(Product, review.product_id) if review else None
    if review is None or product.seller_id != user.id:
        raise HTTPException(404, "Review not found")
    review.seller_response = body.response
    db.commit()
    return SellerReview(id=review.id, product_id=product.id, product_name=product.name, rating=review.rating,
                        body=review.body, author=review.user.name.split()[0], seller_response=review.seller_response,
                        created_at=_aware(review.created_at))
