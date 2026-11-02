from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import Address, User
from app.schemas_commerce import AddressIn, AddressOut

router = APIRouter(prefix="/api/account/addresses", tags=["account"])
MAX_ADDRESSES = 10


def _out(a: Address) -> AddressOut:
    return AddressOut(id=a.id, full_name=a.full_name, phone=a.phone, line1=a.line1, line2=a.line2,
                      city=a.city, state=a.state, pincode=a.pincode, is_default=a.is_default)


def _own(db: Session, user: User, address_id: int) -> Address:
    a = db.get(Address, address_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(404, "Address not found")
    return a


def _make_default(db: Session, user: User, address: Address) -> None:
    for other in db.scalars(select(Address).where(Address.user_id == user.id)):
        other.is_default = other.id == address.id


@router.get("", response_model=list[AddressOut])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Address).where(Address.user_id == user.id)
                      .order_by(Address.is_default.desc(), Address.id)).all()
    return [_out(a) for a in rows]


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def add_address(body: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    if len(existing) >= MAX_ADDRESSES:
        raise HTTPException(409, f"You can save up to {MAX_ADDRESSES} addresses")
    address = Address(user_id=user.id, **body.model_dump())
    db.add(address)
    db.flush()
    if body.is_default or not existing:  # the first address is the default automatically
        _make_default(db, user, address)
    db.commit()
    return _out(address)


@router.patch("/{address_id}", response_model=AddressOut)
def update_address(address_id: int, body: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address = _own(db, user, address_id)
    for k, v in body.model_dump(exclude={"is_default"}).items():
        setattr(address, k, v)
    if body.is_default:
        _make_default(db, user, address)
    db.commit()
    return _out(address)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address = _own(db, user, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        nxt = db.scalar(select(Address).where(Address.user_id == user.id).order_by(Address.id))
        if nxt:
            nxt.is_default = True
    db.commit()
