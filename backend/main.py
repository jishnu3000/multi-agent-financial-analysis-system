"""
Multi-Agent Financial Analysis System
Backend – application entry point.

Project layout:
    core/       config, database, security, llm
    models/     pydantic schemas and AgentState
    services/   stock_data, technical, pdf_generator, workflow (agents)
    routers/    auth, analysis, health

Environment variables:
    OPENAI_API_KEY, OPENAI_MODEL, MONGODB_URL, JWT_SECRET_KEY, ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES, HOST, PORT, CORS_ORIGINS

Usage:
    uvicorn main:app --reload
    # or
    python main.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import auth, analysis, health

# ==================== APPLICATION ====================

app = FastAPI(
    title="Multi-Agent Financial Analysis System",
    description="Multi-Agent Stock Analysis System",
    version="1.0.0",
)

# Ensure the Vite dev server is always allowed even if not in the env list
_cors_origins = list({
    *settings.CORS_ORIGINS,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(analysis.router)

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
