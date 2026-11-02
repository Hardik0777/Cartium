from datetime import timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_role
from app.models import (
    AdminAction, Complaint, ComplaintStatus, ItemStatus, ListingStatus, Order, OrderItem, OrderStatus, Product,
    Refund, RefundStatus, Role, SellerStatus, User, utcnow,
)
from app.schemas_admin import (
    AdminDashboard, AuditRow, ComplaintDecision, ComplaintRow, DayPoint, Flag, ModerationIn, ProductRow,
    RefundDecision, RefundRow, UserRow, UserUpdate,
)
from app.services import razorpay
from app.services.orders import _aware

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin = require_role(Role.admin)

STORE_TZ = ZoneInfo("Asia/Kolkata")  # sales days are counted in India time, not UTC
HIGH_VALUE_ORDER = 25_000       # rupees
ABANDONED_LIMIT = 5             # unpaid checkouts in 24 hours
SELLER_CANCEL_LIMIT = 3         # cancelled items in 7 days


def log(db: Session, who: User, target_type: str, target_id: int, action: str, note: str = "") -> None:
    db.add(AdminAction(admin_id=who.id, target_type=target_type, target_id=target_id, action=action, note=note))


# --------------------------------------------------------------------- users
def _user_row(db: Session, u: User) -> UserRow:
    orders = db.scalar(select(func.count(Order.id)).where(Order.user_id == u.id, Order.status == OrderStatus.paid))
    listings = db.scalar(select(func.count(Product.id)).where(Product.seller_id == u.id))
    return UserRow(id=u.id, name=u.name, email=u.email, role=u.role.value,
                   seller_status=u.seller_status.value if u.seller_status else None, is_active=u.is_active,
                   created_at=_aware(u.created_at), orders=orders, listings=listings)


@router.get("/users", response_model=list[UserRow])
def users(q: str | None = None, role: str | None = None, seller_status: str | None = None,
          me: User = Depends(admin), db: Session = Depends(get_db)):
    query = select(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        query = query.where(User.role == Role(role))
    if seller_status:
        query = query.where(User.seller_status == SellerStatus(seller_status))
    rows = db.scalars(query.order_by(User.created_at.desc(), User.id.desc()).limit(200)).all()
    return [_user_row(db, u) for u in rows]


@router.patch("/users/{user_id}", response_model=UserRow)
def update_user(user_id: int, body: UserUpdate, me: User = Depends(admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == me.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(409, "You can't ban yourself or remove your own admin access")

    if body.role and body.role != user.role.value:
        old = user.role.value
        user.role = Role(body.role)
        # A new seller starts pending; anyone who stops being a seller loses their seller status.
        user.seller_status = SellerStatus.pending if user.role == Role.seller else None
        user.token_version += 1  # make them log in again so their new permissions apply everywhere
        log(db, me, "user", user.id, f"role:{old}->{body.role}", body.note)
    if body.seller_status:
        if user.role != Role.seller:
            raise HTTPException(409, "Only seller accounts have a seller status")
        user.seller_status = SellerStatus(body.seller_status)
        log(db, me, "user", user.id, f"seller:{body.seller_status}", body.note)
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        if not body.is_active:
            user.token_version += 1  # banning logs them out of every device immediately
        log(db, me, "user", user.id, "activated" if body.is_active else "banned", body.note)
    db.commit()
    db.refresh(user)
    return _user_row(db, user)


# ------------------------------------------------------------------ listings
def _product_row(p: Product) -> ProductRow:
    return ProductRow(id=p.id, name=p.name, brand=p.brand, description=p.description, category=p.category.name,
                      price=float(p.price), mrp=float(p.mrp), stock=p.stock, image_url=p.image_url,
                      status=p.status.value, seller_id=p.seller_id, seller_name=p.seller.name,
                      created_at=_aware(p.created_at))


@router.get("/products", response_model=list[ProductRow])
def products(status: str = "pending", q: str | None = None, me: User = Depends(admin), db: Session = Depends(get_db)):
    query = select(Product)
    if status != "all":
        query = query.where(Product.status == ListingStatus(status))
    if q:
        query = query.where(Product.name.ilike(f"%{q.strip()}%"))
    order = Product.created_at.asc() if status == "pending" else Product.created_at.desc()  # oldest waits least
    return [_product_row(p) for p in db.scalars(query.order_by(order, Product.id).limit(200))]


@router.patch("/products/{product_id}/moderation", response_model=ProductRow)
def moderate(product_id: int, body: ModerationIn, me: User = Depends(admin), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(404, "Listing not found")
    if body.status in ("rejected", "removed") and not body.note:
        raise HTTPException(422, "Tell the seller why, so they can fix it")
    p.status = ListingStatus(body.status)
    log(db, me, "product", p.id, body.status, body.note)
    db.commit()
    db.refresh(p)
    return _product_row(p)


# -------------------------------------------------------------------- refunds
def _refund_row(db: Session, r: Refund) -> RefundRow:
    buyer = db.get(User, r.order.user_id)
    return RefundRow(id=r.id, order_id=r.order_id, buyer_name=buyer.name, buyer_email=buyer.email,
                     amount=float(r.amount), reason=r.reason, status=r.status.value,
                     razorpay_payment_id=r.order.razorpay_payment_id, razorpay_refund_id=r.razorpay_refund_id,
                     created_at=_aware(r.created_at), processed_at=_aware(r.processed_at))


@router.get("/refunds", response_model=list[RefundRow])
def refunds(status: str = "requested", me: User = Depends(admin), db: Session = Depends(get_db)):
    query = select(Refund)
    if status != "all":
        query = query.where(Refund.status == RefundStatus(status))
    return [_refund_row(db, r) for r in db.scalars(query.order_by(Refund.created_at.desc(), Refund.id.desc()))]


@router.patch("/refunds/{refund_id}", response_model=RefundRow)
def decide_refund(refund_id: int, body: RefundDecision, me: User = Depends(admin), db: Session = Depends(get_db)):
    refund = db.get(Refund, refund_id, with_for_update=True, populate_existing=True)
    if refund is None:
        raise HTTPException(404, "Refund not found")
    if refund.status != RefundStatus.requested:
        raise HTTPException(409, f"This refund was already {refund.status.value}")  # never refund twice
    if body.action == "reject":
        if not body.note:
            raise HTTPException(422, "Add a note explaining why the refund is rejected")
        refund.status = RefundStatus.rejected
    else:
        payment_id = refund.order.razorpay_payment_id
        if not payment_id:
            raise HTTPException(409, "This order has no Razorpay payment to refund")
        try:
            refund.razorpay_refund_id = razorpay.refund_payment(payment_id, int(refund.amount * 100), refund.reason)
        except razorpay.PaymentsNotConfigured as exc:
            raise HTTPException(503, f"Payments aren't set up. {exc}")
        except razorpay.RazorpayError as exc:
            raise HTTPException(502, str(exc))
        refund.status = RefundStatus.processed
    refund.processed_at = utcnow()
    log(db, me, "refund", refund.id, refund.status.value, body.note)
    db.commit()
    return _refund_row(db, refund)


# ----------------------------------------------------------------- complaints
def complaint_row(c: Complaint) -> ComplaintRow:
    return ComplaintRow(id=c.id, order_id=c.order_id, buyer_name=c.user.name, subject=c.subject, message=c.message,
                        status=c.status.value, admin_reply=c.admin_reply, created_at=_aware(c.created_at),
                        resolved_at=_aware(c.resolved_at))


@router.get("/complaints", response_model=list[ComplaintRow])
def complaints(status: str = "open", me: User = Depends(admin), db: Session = Depends(get_db)):
    query = select(Complaint)
    if status != "all":
        query = query.where(Complaint.status == ComplaintStatus(status))
    return [complaint_row(c) for c in db.scalars(query.order_by(Complaint.created_at.asc(), Complaint.id))]


@router.patch("/complaints/{complaint_id}", response_model=ComplaintRow)
def resolve_complaint(complaint_id: int, body: ComplaintDecision, me: User = Depends(admin), db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(404, "Complaint not found")
    c.admin_reply = body.reply.strip()
    c.status = ComplaintStatus.resolved
    c.resolved_at = utcnow()
    log(db, me, "complaint", c.id, "resolved", body.reply.strip())
    db.commit()
    return complaint_row(c)


# ------------------------------------------------------------- fraud flags
def fraud_flags(db: Session) -> list[Flag]:
    """Simple, explainable rules. They don't block anyone; they point an admin at things worth a look."""
    now = utcnow()
    flags: list[Flag] = []
    for o in db.scalars(select(Order).where(Order.status == OrderStatus.paid, Order.total >= HIGH_VALUE_ORDER)
                        .order_by(Order.created_at.desc()).limit(20)):
        flags.append(Flag(kind="high_value_order", severity="review", order_id=o.id, user_id=o.user_id,
                          message=f"Order #{o.id} is ₹{o.total:,.0f}, above the ₹{HIGH_VALUE_ORDER:,} review limit"))
    abandoned = db.execute(
        select(Order.user_id, func.count(Order.id)).where(
            Order.status == OrderStatus.cancelled, Order.razorpay_payment_id.is_(None),
            Order.created_at >= now - timedelta(hours=24)).group_by(Order.user_id)
        .having(func.count(Order.id) >= ABANDONED_LIMIT)).all()
    for user_id, n in abandoned:
        u = db.get(User, user_id)
        flags.append(Flag(kind="abandoned_checkouts", severity="high", user_id=user_id,
                          message=f"{u.name} started {n} checkouts in 24 hours without paying (stock was held each time)"))
    cancels = db.execute(
        select(OrderItem.seller_id, func.count(OrderItem.id)).where(
            OrderItem.status == ItemStatus.cancelled, OrderItem.status_updated_at >= now - timedelta(days=7))
        .group_by(OrderItem.seller_id).having(func.count(OrderItem.id) >= SELLER_CANCEL_LIMIT)).all()
    for seller_id, n in cancels:
        u = db.get(User, seller_id)
        flags.append(Flag(kind="seller_cancellations", severity="high", user_id=seller_id,
                          message=f"{u.name} cancelled {n} paid items in the last 7 days"))
    return flags


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard", response_model=AdminDashboard)
def dashboard(me: User = Depends(admin), db: Session = Depends(get_db)):
    now = utcnow()
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    paid = db.scalars(select(Order).where(Order.status == OrderStatus.paid)).all()
    since = (now.astimezone(STORE_TZ) - timedelta(days=13)).date()
    days = {(since + timedelta(days=i)).isoformat(): DayPoint(day=(since + timedelta(days=i)).isoformat(), orders=0, revenue=0)
            for i in range(14)}
    for o in paid:
        key = _aware(o.paid_at or o.created_at).astimezone(STORE_TZ).date().isoformat()
        if key in days:
            days[key].orders += 1
            days[key].revenue += float(o.total)
    recent = db.scalars(select(AdminAction).order_by(AdminAction.id.desc()).limit(10)).all()
    return AdminDashboard(
        buyers=count(select(User.id).where(User.role == Role.buyer)),
        sellers=count(select(User.id).where(User.role == Role.seller)),
        new_users_7d=count(select(User.id).where(User.created_at >= now - timedelta(days=7))),
        paid_orders=len(paid),
        gmv=float(sum((o.total for o in paid), Decimal("0"))),
        gmv_30d=float(sum((o.total for o in paid if _aware(o.paid_at or o.created_at) >= now - timedelta(days=30)), Decimal("0"))),
        pending_sellers=count(select(User.id).where(User.role == Role.seller, User.seller_status == SellerStatus.pending)),
        pending_listings=count(select(Product.id).where(Product.status == ListingStatus.pending)),
        refunds_requested=count(select(Refund.id).where(Refund.status == RefundStatus.requested)),
        open_complaints=count(select(Complaint.id).where(Complaint.status == ComplaintStatus.open)),
        last_14_days=list(days.values()),
        flags=fraud_flags(db),
        recent_actions=[AuditRow(id=a.id, admin_name=a.admin.name, target_type=a.target_type, target_id=a.target_id,
                                 action=a.action, note=a.note, created_at=_aware(a.created_at)) for a in recent],
    )
