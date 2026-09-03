"""
server/api/middleware/auth.py

Decorators for JWT-based role enforcement and resource ownership checks.

Usage:
    @jwt_required()
    @require_role("admin")
    def my_view(): ...
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from server.models import User, Donor, Charity


def require_role(*roles):
    """
    Decorator that enforces the current JWT user has one of the given roles.
    Must be applied AFTER @jwt_required().
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or user.role not in roles:
                return jsonify({"error": "Forbidden — insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    """Return the User ORM object for the current JWT identity."""
    user_id = int(get_jwt_identity())
    return User.query.get(user_id)


def get_donor_or_403():
    """
    Return the Donor profile for the current user, or a 403 tuple if the
    user has no donor profile.
    """
    user = current_user()
    if not user or not user.donor:
        return None, (jsonify({"error": "Donor profile not found"}), 403)
    return user.donor, None


def get_charity_or_403():
    """
    Return the Charity profile for the current user, or a 403 tuple.
    """
    user = current_user()
    if not user or not user.charity:
        return None, (jsonify({"error": "Charity profile not found"}), 403)
    return user.charity, None


def require_charity_ownership(charity_id_kwarg: str = "charity_id"):
    """
    Decorator: ensures the logged-in charity user owns the target charity_id
    path parameter.  Admin users bypass this check.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if user.role == "admin":
                return fn(*args, **kwargs)
            if user.role != "charity":
                return jsonify({"error": "Forbidden"}), 403
            target_id = kwargs.get(charity_id_kwarg)
            if not user.charity or user.charity.id != int(target_id):
                return jsonify({"error": "You do not own this charity"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
