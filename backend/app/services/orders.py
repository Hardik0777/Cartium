from datetime import timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Address, Cart, ItemStatus, Order, OrderItem, OrderStatus, Product, User, utcnow,
)
from app.schemas_commerce import OrderItemOut, OrderOut
from app.services.carts import line_problem, shipping_for

PROGRESS_ORDER = [ItemStatus.placed, ItemStatus.packed, ItemStatus.shipped, ItemStatus.delivered]


def _aware(dt):
    # MySQL returns naive datetimes; we always store UTC, so attach the zone back.
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_address(a: Address) -> str:
    parts = [a.line1, a.line2, f"{a.city}, {a.state} {a.pincode}"]
    return "\n".join(p for p in parts if p)


def release_stock(db: Session, order: Order) -> None:
    for item in order.items:
        if item.product_id:
            product = db.get(Product, item.product_id, with_for_update=True, populate_existing=True)
            if product:
                product.stock += item.quantity


def expire_stale_orders(db: Session) -> None:
    """Gives back stock held by checkouts that were never paid. Runs lazily before checkout
    and when orders are listed, so no background scheduler is needed."""
    now = utcnow()
    stale = db.scalars(select(Order).where(Order.status == OrderStatus.pending_payment)).all()
    changed = False
    for order in stale:
        if _aware(order.expires_at) < now:
            release_stock(db, order)
            order.status = OrderStatus.cancelled
            changed = True
    if changed:
        db.commit()


def place_order(db: Session, user: User, cart: Cart, address: Address) -> Order:
    """Reserves stock and creates a pending order. Prices and totals come from the database,
    never from the browser."""
    if not cart.items:
        raise HTTPException(409, "This cart is empty")
    problems = [f"{i.product.name}: {p}" for i in cart.items if (p := line_problem(db, i))]
    if problems:
        raise HTTPException(409, "Fix these items first: " + "; ".join(problems))

    # Lock the product rows (in id order, to avoid deadlocks between two checkouts) so two
    # buyers can't both take the last unit. SELECT ... FOR UPDATE on MySQL.
    # populate_existing matters: these products were already loaded (unlocked) above, and without
    # it SQLAlchemy would hand back those cached copies instead of the values read under the lock,
    # so two checkouts could both see "1 left". The race test in tests/test_orders.py caught this.
    ids = sorted(i.product_id for i in cart.items)
    locked = {p.id: p for p in db.scalars(
        select(Product).where(Product.id.in_(ids)).order_by(Product.id)
        .with_for_update().execution_options(populate_existing=True)
    )}

    subtotal = Decimal("0")
    order = Order(user_id=user.id, cart_name=cart.name, status=OrderStatus.pending_payment,
                  ship_name=address.full_name, ship_phone=address.phone, ship_address=format_address(address),
                  subtotal=0, shipping_fee=0, total=0,
                  expires_at=utcnow() + timedelta(minutes=settings.payment_window_minutes))
    for item in cart.items:
        product = locked[item.product_id]
        if product.stock < item.quantity:  # re-check under the lock
            db.rollback()
            raise HTTPException(409, f"{product.name}: only {product.stock} left")
        product.stock -= item.quantity
        subtotal += product.price * item.quantity
        order.items.append(OrderItem(product_id=product.id, seller_id=product.seller_id, name=product.name,
                                     unit_price=product.price, quantity=item.quantity))
    shipping = shipping_for(subtotal)
    order.subtotal, order.shipping_fee, order.total = subtotal, shipping, subtotal + shipping
    db.add(order)
    db.flush()
    return order


def progress(order: Order) -> str:
    if order.status != OrderStatus.paid:
        return order.status.value
    live = [i.status for i in order.items if i.status != ItemStatus.cancelled]
    if not live:
        return "cancelled"
    # The order is only as far along as its slowest item.
    return min(live, key=PROGRESS_ORDER.index).value


def to_out(db: Session, order: Order) -> OrderOut:
    sellers = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_({i.seller_id for i in order.items})))}
    return OrderOut(
        id=order.id, cart_name=order.cart_name, status=order.status.value, progress=progress(order),
        subtotal=float(order.subtotal), shipping_fee=float(order.shipping_fee), total=float(order.total),
        ship_name=order.ship_name, ship_phone=order.ship_phone, ship_address=order.ship_address,
        created_at=_aware(order.created_at), paid_at=_aware(order.paid_at),
        items=[OrderItemOut(id=i.id, product_id=i.product_id, name=i.name, unit_price=float(i.unit_price),
                            quantity=i.quantity, status=i.status.value,
                            status_updated_at=_aware(i.status_updated_at),
                            seller_name=sellers.get(i.seller_id, "Seller")) for i in order.items],
    )
