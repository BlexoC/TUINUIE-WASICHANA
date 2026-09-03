"""
wsgi.py — WSGI entry point for production (Gunicorn / uWSGI)

Usage:
    gunicorn "wsgi:app" --workers 4 --bind 0.0.0.0:5000
"""

import os
from server import create_app

env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    app.run()
