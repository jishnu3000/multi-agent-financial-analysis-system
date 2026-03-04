"""
Security utilities: password hashing, JWT creation and validation,
and the FastAPI dependency that resolves the current authenticated user.
"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from core.config import settings
from core.database import users_collection

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches the bcrypt *hashed_password*."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode(
            "utf-8") if isinstance(hashed_password, str) else hashed_password,
    )


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Encode *data* as a signed JWT with an expiry claim.

    Args:
        data:          Payload dict (must include ``"sub"`` = username).
        expires_delta: Custom lifetime; defaults to
                       ``settings.ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

_credentials_exception = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: decode the bearer token and return the user document.

    Raises:
        HTTPException(401): If the token is invalid or the user no longer exists.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise _credentials_exception
    except jwt.PyJWTError:
        raise _credentials_exception

    user = users_collection.find_one({"username": username})
    if user is None:
        raise _credentials_exception
    return user
