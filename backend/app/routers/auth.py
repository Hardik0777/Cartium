from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import OAuthIdentity, Role, SellerStatus, User
from app.schemas import ChooseRole, GoogleSignIn, LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services import google

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


@router.get("/config")
def auth_config():
    """Tells the frontend whether to show the Google button (the client ID isn't secret)."""
    from app.core.config import settings
    return {"google_client_id": settings.google_client_id or None}


@router.post("/oauth", response_model=TokenResponse | ChooseRole)
def google_sign_in(body: GoogleSignIn, db: Session = Depends(get_db)):
    try:
        g = google.verify_id_token(body.credential)
    except google.GoogleNotConfigured as exc:
        raise HTTPException(503, f"Google sign-in isn't set up. {exc}")
    except google.InvalidGoogleToken as exc:
        raise HTTPException(401, str(exc))

    identity = db.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == "google", OAuthIdentity.subject == g.subject))
    user = db.get(User, identity.user_id) if identity else None

    if user is None:
        # Same verified email as an existing account: link Google to it, keep their role.
        user = db.scalar(select(User).where(User.email == g.email))
        if user is None:
            if body.role is None:
                return ChooseRole(name=g.name, email=g.email)  # first visit: ask Shop or Sell
            role = Role(body.role)
            user = User(name=g.name[:100], email=g.email, password_hash=None, role=role,
                        seller_status=SellerStatus.pending if role == Role.seller else None)
            db.add(user)
            db.flush()
        db.add(OAuthIdentity(user_id=user.id, provider="google", subject=g.subject, email=g.email))
        try:
            db.commit()
        except IntegrityError:  # a double click raced us to create the same account; use theirs
            db.rollback()
            identity = db.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == "google",
                                                             OAuthIdentity.subject == g.subject))
            if identity is None:
                raise HTTPException(409, "Couldn't finish signing in. Try again.")
            user = db.get(User, identity.user_id)
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated")
    return _token_response(user)
