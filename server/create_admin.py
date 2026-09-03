"""
server/create_admin.py — Safely create ONE admin account.

Unlike seed.py, this does NOT drop or touch any existing data — it only
inserts a single admin user (and its Administrator profile row), and does
nothing if that email is already taken.

Run with:
    python -m server.create_admin

To target Render's production database from your own machine instead of
your local one, set DATABASE_URL first, e.g.:
    DATABASE_URL="postgresql://...render-connection-string..." python -m server.create_admin

Or run it directly in Render's Shell tab (Render's environment already has
the correct DATABASE_URL set, so no need to pass it there).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from server import create_app, db
from server.models import User, Administrator

# --- Edit these before running if you want different credentials ----------
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@tuinuewasichana.org"
ADMIN_PASSWORD = "ChangeMe123!"
# ---------------------------------------------------------------------------


def run():
    app = create_app("production")
    with app.app_context():
        existing = User.query.filter_by(email=ADMIN_EMAIL).first()
        if existing:
            print(f"A user with email {ADMIN_EMAIL} already exists (id={existing.id}, role={existing.role}).")
            if existing.role != "admin":
                print("That account is NOT an admin — pick a different email above and re-run.")
            else:
                print("It's already an admin. Nothing to do.")
            return

        user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            password_hash=generate_password_hash(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()  # get user.id

        db.session.add(Administrator(user_id=user.id))
        db.session.commit()

        print("✅ Admin account created.")
        print(f"   Email:    {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")
        print("   Log in with these on the deployed site's Sign In form.")


if __name__ == "__main__":
    run()
