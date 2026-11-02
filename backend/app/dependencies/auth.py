from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import Role, SellerStatus, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    # Token is rejected if the user was deleted, banned, or has logged out since it was issued.
    if user is None or payload.get("ver") != user.token_version:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user, but returns None for visitors instead of raising.
    Used on public pages that add extras (wishlist hearts, recently viewed) for logged-in users."""
    if creds is None:
        return None
    try:
        return get_current_user(creds, db)
    except HTTPException:
        return None


def require_role(*roles: Role) -> Callable[..., User]:
    """Usage: user: User = Depends(require_role(Role.admin))"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this page")
        return user

    return checker


def require_approved_seller(user: User = Depends(require_role(Role.seller))) -> User:
    if user.seller_status != SellerStatus.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your seller account is waiting for admin approval")
    return user
