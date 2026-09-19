"""Entrypoint for Vercel deployment and uvicorn execution."""

from app.main import app

__all__ = ["app"]
