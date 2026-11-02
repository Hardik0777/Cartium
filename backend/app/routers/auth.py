from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import Role, SellerStatus, User
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(user.id, user.role.value, user.token_version)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    role = Role(body.role)
    user = User(
        name=body.name,
        email=email,
        password_hash=hash_password(body.password),
        role=role,
        seller_status=SellerStatus.pending if role == Role.seller else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Same message for "no such email" and "wrong password", so attackers can't probe which emails exist.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invalidates every token issued to this user so far (logs out all devices)."""
    user.token_version += 1
    db.commit()
    return {"logged_out": True}
