from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.dependencies.auth import require_role
from app.models import Address, CartItem, Order, OrderStatus, Role, User, utcnow
from app.schemas_commerce import CheckoutIn, CheckoutOut, OrderOut, ReorderOut, VerifyIn
from app.services import carts, orders, razorpay
from app.services.catalog import is_visible

router = APIRouter(prefix="/api/orders", tags=["orders"])
buyer = require_role(Role.buyer)


def _own_order(db: Session, user: User, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    return order


@router.post("/razorpay/create", response_model=CheckoutOut)
def create_checkout(body: CheckoutIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    orders.expire_stale_orders(db)
    cart = carts.own_cart(db, user, body.cart_id)
    address = db.get(Address, body.address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(404, "Address not found")

    order = orders.place_order(db, user, cart, address)
    amount_paise = int(order.total * 100)
    try:
        order.razorpay_order_id = razorpay.create_order(amount_paise, receipt=f"cartium-{order.id}")
    except razorpay.PaymentsNotConfigured as exc:
        db.rollback()  # nothing was reserved
        raise HTTPException(503, f"Payments aren't set up yet. {exc}")
    except razorpay.RazorpayError as exc:
        db.rollback()
        raise HTTPException(502, str(exc))
    db.commit()
    return CheckoutOut(order_id=order.id, razorpay_order_id=order.razorpay_order_id, amount=amount_paise,
                       currency="INR", key_id=settings.razorpay_key_id, name=user.name, email=user.email,
                       contact=address.phone)


@router.post("/razorpay/verify", response_model=OrderOut)
def verify_payment(body: VerifyIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.razorpay_order_id == body.razorpay_order_id)
                      .with_for_update().execution_options(populate_existing=True))
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    if not razorpay.signature_is_valid(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "Payment couldn't be verified. If money was deducted, it will be refunded automatically.")
    if order.status == OrderStatus.paid:
        return orders.to_out(db, order)  # verifying twice (e.g. a double click) is harmless
    if order.status == OrderStatus.cancelled:
        # Paid after the reservation lapsed. Rare; needs a manual refund (admin tools, Phase 5).
        raise HTTPException(409, "This checkout expired before payment finished. Contact support for a refund.")

    order.status = OrderStatus.paid
    order.razorpay_payment_id = body.razorpay_payment_id
    order.paid_at = utcnow()
    # Empty the cart that was checked out (only the products that were ordered).
    ordered = {i.product_id for i in order.items}
    for item in db.scalars(select(CartItem).join(CartItem.cart).where(CartItem.product_id.in_(ordered))):
        if item.cart.user_id == user.id and item.cart.name == order.cart_name:
            db.delete(item)
    db.commit()
    return orders.to_out(db, order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_checkout(order_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    """Called when the buyer closes the payment window. Gives the reserved stock back."""
    order = _own_order(db, user, order_id)
    if order.status != OrderStatus.pending_payment:
        raise HTTPException(409, "Only unpaid checkouts can be cancelled here")
    orders.release_stock(db, order)
    order.status = OrderStatus.cancelled
    db.commit()
    return orders.to_out(db, order)


@router.get("", response_model=list[OrderOut])
def list_orders(user: User = Depends(buyer), db: Session = Depends(get_db)):
    orders.expire_stale_orders(db)
    rows = db.scalars(select(Order).where(Order.user_id == user.id, Order.status == OrderStatus.paid)
                      .order_by(Order.created_at.desc(), Order.id.desc())).all()
    return [orders.to_out(db, o) for o in rows]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    return orders.to_out(db, _own_order(db, user, order_id))


@router.post("/{order_id}/reorder", response_model=ReorderOut)
def reorder(order_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    """Puts everything from a past order back into the active cart, skipping what's unavailable."""
    order = _own_order(db, user, order_id)
    cart = carts.active_cart(db, user)
    added, skipped = [], []
    for item in order.items:
        product = is_visible(db, item.product_id) if item.product_id else None
        if product is None or product.stock <= 0:
            skipped.append(item.name)
            continue
        try:
            carts.add_item(db, cart, product.id, min(item.quantity, product.stock))
            added.append(item.name)
        except HTTPException:
            skipped.append(item.name)  # e.g. already at the maximum in the cart
    db.commit()
    return ReorderOut(cart_id=cart.id, added=added, skipped=skipped)
