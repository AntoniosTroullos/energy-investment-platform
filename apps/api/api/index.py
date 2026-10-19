"""Vercel's Python runtime looks for an ASGI/WSGI app under /api. The real
FastAPI app lives at app/main.py (used directly by `uvicorn app.main:app`
locally); this just re-exports it so Vercel's zero-config detection finds it.
"""

from app.main import app

__all__ = ["app"]
