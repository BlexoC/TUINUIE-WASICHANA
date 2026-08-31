"""
server/api/routes/auth.py

POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash

from server import db
from server.models import User, Donor, Administrator

auth_bp = Blueprint("auth", __name__)

# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------
@auth_bp.post("/register")
def register():
    """
    Register a new donor or charity-applicant user.
    Admins are provisioned directly in the database (not via this endpoint).

    Body (JSON):
        username    str  required
        email       str  required
        password    str  required  (min 8 chars)
        role        str  required  "donor" | "charity"
        first_name  str  optional
        last_name   str  optional
        phone       str  optional
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ("username", "email", "password", "role")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    if data["role"] not in ("donor", "charity"):
        return jsonify({"error": "role must be 'donor' or 'charity'"}), 422

    if len(data["password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 422

    if User.query.filter(
        (User.email == data["email"].lower()) | (User.username == data["username"])
    ).first():
        return jsonify({"error": "Email or username already in use"}), 409

    user = User(
        username=data["username"].strip(),
        email=data["email"].lower().strip(),
        password_hash=generate_password_hash(data["password"]),
        role=data["role"],
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        phone=data.get("phone"),
    )
    db.session.add(user)
    db.session.flush()  # get user.id before committing

    # Create the matching profile row
    if data["role"] == "donor":
        db.session.add(Donor(user_id=user.id, default_anonymous=False))

    db.session.commit()

    access_token  = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "message": "Registration successful",
        "user": _user_dict(user),
        "access_token":  access_token,
        "refresh_token": refresh_token,
    }), 201


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------
@auth_bp.post("/login")
def login():
    """
    Authenticate with email + password.
    Returns access + refresh JWT tokens.
    """
    data = request.get_json(silent=True) or {}
    email    = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 422

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account is deactivated"}), 403

    access_token  = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "user": _user_dict(user),
        "access_token":  access_token,
        "refresh_token": refresh_token,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------
@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """
    Exchange a valid refresh token for a new access token.
    Send the refresh token in Authorization: Bearer <refresh_token>.
    """
    user_id = get_jwt_identity()
    new_token = create_access_token(identity=user_id)
    return jsonify({"access_token": new_token}), 200


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------
@auth_bp.post("/logout")
@jwt_required()
def logout():
    """
    Client-side logout.
    In production add the jti to a Redis blocklist:
        jti = get_jwt()["jti"]
        redis.set(jti, "", ex=app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    """
    return jsonify({"message": "Logged out successfully"}), 200


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------
@auth_bp.get("/me")
@jwt_required()
def me():
    """Return the profile of the currently authenticated user."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_dict(user, detailed=True)), 200


# ---------------------------------------------------------------------------
# Internal serializer
# ---------------------------------------------------------------------------
def _user_dict(user: User, detailed: bool = False) -> dict:
    base = {
        "id":         user.id,
        "username":   user.username,
        "email":      user.email,
        "role":       user.role,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "is_active":  user.is_active,
    }
    if detailed:
        base["phone"]      = user.phone
        base["created_at"] = user.created_at.isoformat() if user.created_at else None
        if user.donor:
            base["donor_id"] = user.donor.id
        if user.charity:
            base["charity_id"] = user.charity.id
    return base
