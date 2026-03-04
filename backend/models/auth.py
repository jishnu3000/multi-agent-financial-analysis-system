"""Pydantic models for authentication endpoints."""

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Request body for ``POST /register``."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class Token(BaseModel):
    """Response body for ``POST /login``."""

    access_token: str
    token_type: str
