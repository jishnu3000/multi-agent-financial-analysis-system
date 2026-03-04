"""
Application configuration.

All runtime settings are read from environment variables (via python-dotenv).
Import the ``settings`` singleton in any module that needs config values.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Google Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # MongoDB
    MONGODB_URL: str = os.getenv(
        "MONGODB_URL",
        "mongodb+srv://jishnu455:<db_password>@cluster0.npr7jys.mongodb.net/?appName=Cluster0",
    )

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "fallback_secret_key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    )

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

    # CORS – comma-separated list of allowed origins
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]


settings = Settings()

if not settings.GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")
