from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Cart, CartItem, User
from app.schemas_catalog import ProductCard
from app.schemas_commerce import CartDetail, CartLine, CartSummary
from app.services.catalog import is_visible

MAX_CARTS = 10
MAX_QTY = 10
DEFAULT_NAME = "My cart"


def shipping_for(subtotal: Decimal) -> Decimal:
    if subtotal == 0 or subtotal >= settings.free_shipping_over:
        return Decimal("0")
    return Decimal(settings.shipping_fee)


def active_cart(db: Session, user: User) -> Cart:
    """The cart new items go into. Every buyer always has one; it's created on first use."""
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id, Cart.is_active.is_(True)))
    if cart is None:
        cart = db.scalar(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id))
        if cart is None:
            cart = Cart(user_id=user.id, name=DEFAULT_NAME)
            db.add(cart)
        cart.is_active = True
        db.commit()
        db.refresh(cart)
    return cart


def own_cart(db: Session, user: User, cart_id: int) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None or cart.user_id != user.id:  # 404, not 403: don't reveal other people's carts exist
        raise HTTPException(404, "Cart not found")
    return cart


def activate(db: Session, user: User, cart: Cart) -> None:
    for other in db.scalars(select(Cart).where(Cart.user_id == user.id, Cart.is_active.is_(True))):
        other.is_active = False
    cart.is_active = True


def summarize(db: Session, cart: Cart) -> CartSummary:
    subtotal = sum((i.product.price * i.quantity for i in cart.items), Decimal("0"))
    return CartSummary(id=cart.id, name=cart.name, is_active=cart.is_active,
                       item_count=sum(i.quantity for i in cart.items), subtotal=float(subtotal))


def line_problem(db: Session, item: CartItem) -> str | None:
    product = is_visible(db, item.product_id)
    if product is None:
        return "No longer available"
    if product.stock <= 0:
        return "Out of stock"
    if item.quantity > product.stock:
        return f"Only {product.stock} left; lower the quantity"
    return None


def detail(db: Session, cart: Cart) -> CartDetail:
    lines, subtotal = [], Decimal("0")
    for item in cart.items:
        problem = line_problem(db, item)
        line_total = item.product.price * item.quantity
        if problem is None:
            subtotal += line_total  # only items that can actually be bought count towards the total
        lines.append(CartLine(id=item.id, product=ProductCard.of(item.product), quantity=item.quantity,
                              line_total=float(line_total), problem=problem))
    shipping = shipping_for(subtotal)
    return CartDetail(
        id=cart.id, name=cart.name, is_active=cart.is_active,
        item_count=sum(i.quantity for i in cart.items), subtotal=float(subtotal),
        lines=lines, shipping_fee=float(shipping), total=float(subtotal + shipping),
        can_checkout=bool(lines) and all(line.problem is None for line in lines),
    )


def add_item(db: Session, cart: Cart, product_id: int, quantity: int) -> None:
    product = is_visible(db, product_id)
    if product is None:
        raise HTTPException(404, "This product isn't available")
    if product.stock <= 0:
        raise HTTPException(409, "This product is out of stock")
    item = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
    current = item.quantity if item else 0
    wanted = min(current + quantity, MAX_QTY, product.stock)
    if wanted == current:
        raise HTTPException(409, f"You already have the maximum available ({current}) in this cart")
    if item:
        item.quantity = wanted
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product_id, quantity=wanted))
