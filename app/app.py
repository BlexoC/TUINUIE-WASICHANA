"""Compatibility layer package so tests can import `app.*`.

This proxies to the `server.app` package where the application code lives.
"""
from server.app.app import create_app, db

# Provide a default application for convenience
try:
    default_app = create_app()
except Exception:
    default_app = None


__all__ = ["create_app", "db", "default_app"]
