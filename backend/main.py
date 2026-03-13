"""
Collections Intelligence Platform — FastAPI Backend
Main application entry point.

Registers:
  - All routers (auth, customer, grace, restructure, chat, preferences, officer)
  - CORS middleware (allows React frontend on localhost:3000)
  - Startup event: DB table creation + seeding + Chroma policy seeding

Run with:
  uvicorn backend.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.db.database import engine, Base
from backend.db.seed_data import seed

from backend.routers.auth        import router as auth_router
from backend.routers.customer    import router as customer_router
from backend.routers.grace       import router as grace_router
from backend.routers.restructure import router as restructure_router
from backend.routers.chat        import router as chat_router
from backend.routers.preferences import router as preferences_router
from backend.routers.officer     import router as officer_router


# ─────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup:
      1. Create all SQL tables
      2. Seed database with dummy data
      3. Seed Chroma vector DB with policy documents
    """
    print("🚀 Collections Intelligence Platform starting up...")

    # ── Create SQL tables ─────────────────────────────────────────
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created.")

    # ── Seed SQL data ─────────────────────────────────────────────
    try:
        seed()
    except Exception as e:
        print(f"⚠️  Seed data warning: {e}")

    # ── Seed Chroma policy documents ──────────────────────────────
    try:
        from backend.vector.chroma_store import seed_policy_documents
        seed_policy_documents()
    except Exception as e:
        print(f"⚠️  Chroma seed warning (non-critical): {e}")

    print("✅ Platform ready.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────
    print("🛑 Collections Intelligence Platform shutting down.")


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title       = "Collections Intelligence Platform",
    description = (
        "AI-driven platform for proactive loan collections, "
        "borrower engagement, and recovery strategy recommendations."
    ),
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)


# ─────────────────────────────────────────────
# CORS Middleware
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = [
        "http://localhost:3000",    # React dev server
        "http://127.0.0.1:3000",
        "http://localhost:5173",    # Vite dev server (if used)
        "http://127.0.0.1:5173",
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────
# Register Routers
# ─────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(customer_router)
app.include_router(grace_router)
app.include_router(restructure_router)
app.include_router(chat_router)
app.include_router(preferences_router)
app.include_router(officer_router)


# ─────────────────────────────────────────────
# Root Health Check
# ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "platform": "Collections Intelligence Platform",
        "version":  "1.0.0",
        "status":   "running",
        "docs":     "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint for monitoring.
    """
    from backend.db.database import SessionLocal
    from backend.db.models import Customer, Loan

    db = SessionLocal()
    try:
        customer_count = db.query(Customer).count()
        loan_count     = db.query(Loan).count()
        db_status      = "connected"
    except Exception as e:
        customer_count = 0
        loan_count     = 0
        db_status      = f"error: {str(e)}"
    finally:
        db.close()

    # Check Ollama
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        ollama_status = "running" if r.status_code == 200 else "unavailable"
    except Exception:
        ollama_status = "unavailable (fallback mode active)"

    # Check Chroma
    try:
        from backend.vector.chroma_store import get_chroma_client
        get_chroma_client()
        chroma_status = "connected"
    except Exception as e:
        chroma_status = f"unavailable: {str(e)}"

    return {
        "status":         "healthy",
        "database":       db_status,
        "customers":      customer_count,
        "loans":          loan_count,
        "ollama":         ollama_status,
        "chroma":         chroma_status,
        "llm_model":      "llama3",
    }


# ─────────────────────────────────────────────
# __init__.py files needed for Python imports
# ─────────────────────────────────────────────
# These are created separately as empty files.
