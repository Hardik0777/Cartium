import json
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import assistant, index
from app.core.config import settings
from app.database import get_db
from app.dependencies.auth import require_role
from app.models import ChatMessage, Order, Role, User
from app.schemas_catalog import ProductCard
from app.services.catalog import is_visible
from app.services.orders import progress

router = APIRouter(prefix="/api/ai", tags=["assistant"])
buyer = require_role(Role.buyer)
RATE_LIMIT = 20  # messages per user per minute; each one costs a model call
_recent: dict[int, deque] = defaultdict(deque)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class OrderBrief(BaseModel):
    id: int
    progress: str
    total: float
    items: int


class ChatOut(BaseModel):
    role: str
    text: str
    products: list[ProductCard] = []
    orders: list[OrderBrief] = []
    action: dict | None = None
    source: str | None = None


def _rate_limit(user_id: int) -> None:
    now, q = time.monotonic(), _recent[user_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "You're sending messages very fast. Wait a moment and try again.")
    q.append(now)


def _expand(db: Session, user: User, role: str, text: str, payload: dict) -> ChatOut:
    products = [ProductCard.of(p) for pid in payload.get("products", []) if (p := is_visible(db, pid))]
    orders = []
    for oid in payload.get("orders", []):
        o = db.get(Order, oid)
        if o and o.user_id == user.id:
            orders.append(OrderBrief(id=o.id, progress=progress(o), total=float(o.total), items=len(o.items)))
    return ChatOut(role=role, text=text, products=products, orders=orders,
                   action=payload.get("action"), source=payload.get("source"))


@router.get("/health")
def health():
    return {"model": settings.ai_model_name, "model_configured": bool(settings.huggingface_api_key), **index.health()}


@router.post("/ingest")
def ingest(user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    try:
        return index.rebuild(db)
    except Exception as exc:
        raise HTTPException(503, f"Couldn't build the assistant's index: {type(exc).__name__}. "
                                 "The embedding model downloads on first use; check the internet connection.")


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    _rate_limit(user.id)
    try:
        reply = assistant.respond(db, user, body.message.strip())
    except Exception as exc:  # index unavailable, etc.
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(503, "The assistant isn't available right now. You can still search the store.") from exc
    return _expand(db, user, "assistant", reply.text, {"products": reply.products, "orders": reply.orders,
                                                       "action": reply.action, "source": reply.source})


@router.get("/history", response_model=list[ChatOut])
def history(user: User = Depends(buyer), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.id.desc()).limit(40)).all()
    return [_expand(db, user, r.role, r.content, json.loads(r.payload) if r.payload else {}) for r in reversed(rows)]


@router.delete("/history", status_code=204)
def clear_history(user: User = Depends(buyer), db: Session = Depends(get_db)):
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
    db.commit()
