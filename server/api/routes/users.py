"""
server/api/routes/users.py

GET   /api/users/<id>          — public profile
PATCH /api/users/<id>          — own profile update
PATCH /api/users/<id>/password — change password
GET   /api/users/<id>/reminder — get donation reminder preference (donor)
PUT   /api/users/<id>/reminder — upsert reminder
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from werkzeug.security import generate_password_hash, check_password_hash

from server import db
from server.models import User, DonationReminder
from server.api.middleware.auth import current_user

users_bp = Blueprint("users", __name__)


def _own_or_admin(target_id: int):
    """Return (user, error_tuple).  Enforce that caller is the user or admin."""
    caller = current_user()
    if caller.role != "admin" and caller.id != target_id:
        return None, (jsonify({"error": "Forbidden"}), 403)
    return caller, None


# ---------------------------------------------------------------------------
# GET /api/users/<id>
# ---------------------------------------------------------------------------
@users_bp.get("/<int:user_id>")
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    caller = current_user()
    detailed = (caller.id == user_id or caller.role == "admin")
    return jsonify(_user_dict(user, detailed=detailed)), 200


# ---------------------------------------------------------------------------
# PATCH /api/users/<id>
# ---------------------------------------------------------------------------
@users_bp.patch("/<int:user_id>")
@jwt_required()
def update_user(user_id):
    caller, err = _own_or_admin(user_id)
    if err:
        return err
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    for field in ("first_name", "last_name", "phone"):
        if field in data:
            setattr(user, field, data[field])

    # Donor-specific: default_anonymous preference
    if user.donor and "default_anonymous" in data:
        user.donor.default_anonymous = bool(data["default_anonymous"])

    db.session.commit()
    return jsonify(_user_dict(user, detailed=True)), 200


# ---------------------------------------------------------------------------
# PATCH /api/users/<id>/password
# ---------------------------------------------------------------------------
@users_bp.patch("/<int:user_id>/password")
@jwt_required()
def change_password(user_id):
    caller, err = _own_or_admin(user_id)
    if err:
        return err
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "current_password and new_password required"}), 422
    if not check_password_hash(user.password_hash, data["current_password"]):
        return jsonify({"error": "Current password is incorrect"}), 401
    if len(data["new_password"]) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 422

    user.password_hash = generate_password_hash(data["new_password"])
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200


# ---------------------------------------------------------------------------
# GET /api/users/<id>/reminder
# ---------------------------------------------------------------------------
@users_bp.get("/<int:user_id>/reminder")
@jwt_required()
def get_reminder(user_id):
    caller, err = _own_or_admin(user_id)
    if err:
        return err
    user = User.query.get_or_404(user_id)
    if not user.donor:
        return jsonify({"error": "User is not a donor"}), 403
    if not user.donor.reminder:
        return jsonify({"reminder": None}), 200
    r = user.donor.reminder
    return jsonify({"reminder": {
        "id":           r.id,
        "day_of_month": r.day_of_month,
        "time_of_day":  r.time_of_day.strftime("%H:%M") if r.time_of_day else None,
        "is_enabled":   r.is_enabled,
    }}), 200


# ---------------------------------------------------------------------------
# PUT /api/users/<id>/reminder
# ---------------------------------------------------------------------------
@users_bp.put("/<int:user_id>/reminder")
@jwt_required()
def upsert_reminder(user_id):
    caller, err = _own_or_admin(user_id)
    if err:
        return err
    user = User.query.get_or_404(user_id)
    if not user.donor:
        return jsonify({"error": "User is not a donor"}), 403

    data = request.get_json(silent=True) or {}
    day = data.get("day_of_month")
    if day is None or not (1 <= int(day) <= 31):
        return jsonify({"error": "day_of_month must be 1-31"}), 422

    from datetime import time as dtime
    time_str = data.get("time_of_day", "09:00")
    try:
        h, m = map(int, time_str.split(":"))
        tod = dtime(h, m)
    except Exception:
        return jsonify({"error": "time_of_day must be HH:MM"}), 422

    r = user.donor.reminder
    if r:
        r.day_of_month = int(day)
        r.time_of_day  = tod
        r.is_enabled   = bool(data.get("is_enabled", True))
    else:
        r = DonationReminder(
            donor_id=user.donor.id,
            day_of_month=int(day),
            time_of_day=tod,
            is_enabled=bool(data.get("is_enabled", True)),
        )
        db.session.add(r)

    db.session.commit()
    return jsonify({"message": "Reminder saved", "day_of_month": r.day_of_month}), 200


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------
def _user_dict(user: User, detailed: bool = False) -> dict:
    base = {
        "id":        user.id,
        "username":  user.username,
        "email":     user.email,
        "role":      user.role,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "is_active":  user.is_active,
    }
    if detailed:
        base["phone"] = user.phone
        base["created_at"] = user.created_at.isoformat() if user.created_at else None
    return base
