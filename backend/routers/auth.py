"""
Authentication routes: /register and /login.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from core.database import users_collection
from core.security import create_access_token, get_password_hash, verify_password
from core.config import settings
from models.auth import Token, UserCreate

router = APIRouter(tags=["auth"])


@router.post("/register")
async def register(user: UserCreate):
    """Register a new user account.

    Args:
        user: :class:`~models.auth.UserCreate` with ``username`` and ``password``.

    Returns:
        Confirmation message on success.

    Raises:
        HTTPException(400): If the username is already taken.
    """
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(
            status_code=400, detail="Username already registered")

    users_collection.insert_one(
        {"username": user.username,
            "hashed_password": get_password_hash(user.password)}
    )
    return {"message": "User created successfully"}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate a user and return a JWT bearer token.

    Args:
        form_data: OAuth2 ``username`` / ``password`` form fields.

    Returns:
        :class:`~models.auth.Token` with ``access_token`` and ``token_type``.

    Raises:
        HTTPException(401): On invalid credentials.
    """
    user = users_collection.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}
