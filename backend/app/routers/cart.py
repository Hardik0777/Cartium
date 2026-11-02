from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_role
from app.models import Cart, CartItem, Role, User
from app.schemas_commerce import CartCreate, CartDetail, CartItemAdd, CartItemUpdate, CartRename, CartSummary
from app.services import carts

router = APIRouter(prefix="/api/cart", tags=["cart"])
buyer = require_role(Role.buyer)


def _own_item(db: Session, user: User, item_id: int) -> CartItem:
    item = db.get(CartItem, item_id)
    if item is None or item.cart.user_id != user.id:
        raise HTTPException(404, "Item not found")
    return item


@router.get("", response_model=CartDetail)
def get_active(cart_id: int | None = None, user: User = Depends(buyer), db: Session = Depends(get_db)):
    cart = carts.own_cart(db, user, cart_id) if cart_id else carts.active_cart(db, user)
    return carts.detail(db, cart)


@router.post("", response_model=CartDetail, status_code=status.HTTP_201_CREATED)
def add(body: CartItemAdd, user: User = Depends(buyer), db: Session = Depends(get_db)):
    cart = carts.own_cart(db, user, body.cart_id) if body.cart_id else carts.active_cart(db, user)
    carts.add_item(db, cart, body.product_id, body.quantity)
    db.commit()
    db.refresh(cart)
    return carts.detail(db, cart)


@router.patch("/{item_id}", response_model=CartDetail)
def update_item(item_id: int, body: CartItemUpdate, user: User = Depends(buyer), db: Session = Depends(get_db)):
    item = _own_item(db, user, item_id)
    source = item.cart
    if body.cart_id is not None and body.cart_id != item.cart_id:
        target = carts.own_cart(db, user, body.cart_id)
        quantity = body.quantity or item.quantity
        db.delete(item)
        db.flush()
        carts.add_item(db, target, item.product_id, quantity)  # merges with an existing line there
        db.commit()
        db.refresh(source)
        return carts.detail(db, source)
    if body.quantity == 0:
        db.delete(item)
    elif body.quantity is not None:
        stock = item.product.stock
        if body.quantity > stock:
            raise HTTPException(409, f"Only {stock} left in stock")
        item.quantity = body.quantity
    db.commit()
    db.refresh(source)
    return carts.detail(db, source)


@router.delete("/{item_id}", response_model=CartDetail)
def remove_item(item_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    item = _own_item(db, user, item_id)
    cart = item.cart
    db.delete(item)
    db.commit()
    db.refresh(cart)
    return carts.detail(db, cart)


# ------------------------------------------------------------- named carts
@router.get("/carts", response_model=list[CartSummary])
def list_carts(user: User = Depends(buyer), db: Session = Depends(get_db)):
    carts.active_cart(db, user)  # make sure at least one exists
    rows = db.scalars(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id)).all()
    return [carts.summarize(db, c) for c in rows]


@router.post("/carts", response_model=CartSummary, status_code=status.HTTP_201_CREATED)
def create_cart(body: CartCreate, user: User = Depends(buyer), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count(Cart.id)).where(Cart.user_id == user.id))
    if count >= carts.MAX_CARTS:
        raise HTTPException(409, f"You can have up to {carts.MAX_CARTS} carts")
    cart = Cart(user_id=user.id, name=body.name)
    db.add(cart)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"You already have a cart called “{body.name}”")
    if body.activate or count == 0:
        carts.activate(db, user, cart)
    db.commit()
    db.refresh(cart)
    return carts.summarize(db, cart)


@router.patch("/carts/{cart_id}", response_model=CartSummary)
def rename_cart(cart_id: int, body: CartRename, user: User = Depends(buyer), db: Session = Depends(get_db)):
    cart = carts.own_cart(db, user, cart_id)
    cart.name = body.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"You already have a cart called “{body.name}”")
    db.refresh(cart)
    return carts.summarize(db, cart)


@router.patch("/carts/{cart_id}/activate", response_model=CartSummary)
def activate_cart(cart_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    cart = carts.own_cart(db, user, cart_id)
    carts.activate(db, user, cart)
    db.commit()
    db.refresh(cart)
    return carts.summarize(db, cart)


@router.delete("/carts/{cart_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cart(cart_id: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    cart = carts.own_cart(db, user, cart_id)
    was_active = cart.is_active
    db.delete(cart)
    db.flush()
    if was_active:  # hand the "active" role to another cart, if any
        nxt = db.scalar(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id))
        if nxt:
            nxt.is_active = True
    db.commit()
