"""Verifies Google ID tokens from "Sign in with Google".
Docs: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token"""
from dataclasses import dataclass
from functools import lru_cache

import jwt

from app.core.config import settings

ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleNotConfigured(Exception):
    pass


class InvalidGoogleToken(Exception):
    pass


@dataclass
class GoogleUser:
    subject: str
    email: str
    name: str


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)  # Google rotates keys; cache for an hour


def verify_id_token(credential: str) -> GoogleUser:
    if not settings.google_client_id:
        raise GoogleNotConfigured("Add GOOGLE_CLIENT_ID to backend/.env")
    try:
        signing_key = _jwks_client(settings.google_jwks_url).get_signing_key_from_jwt(credential)
        claims = jwt.decode(
            credential,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,  # issued for OUR app, not some other site's
            options={"require": ["exp", "iat", "iss", "sub", "aud", "email"]},
            leeway=30,
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise InvalidGoogleToken("Couldn't reach Google to check the sign-in. Try again.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidGoogleToken("Google sign-in couldn't be verified. Try again.") from exc
    if claims["iss"] not in ISSUERS:
        raise InvalidGoogleToken("Sign-in token wasn't issued by Google")
    if not claims.get("email_verified"):
        raise InvalidGoogleToken("Your Google email address isn't verified yet")
    return GoogleUser(subject=claims["sub"], email=claims["email"].lower(),
                      name=claims.get("name") or claims["email"].split("@")[0])
