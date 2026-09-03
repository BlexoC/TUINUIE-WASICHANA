"""
server/api/routes/beneficiaries.py

GET    /api/beneficiaries?charity_id=  — list (public)
POST   /api/beneficiaries              — charity adds a beneficiary
GET    /api/beneficiaries/<id>         — detail (public)
PATCH  /api/beneficiaries/<id>         — charity or admin update
DELETE /api/beneficiaries/<id>         — charity or admin delete
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import Beneficiary, Charity
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

beneficiaries_bp = Blueprint("beneficiaries", __name__)


@beneficiaries_bp.get("/")
def list_beneficiaries():
    charity_id = request.args.get("charity_id", type=int)
    query = Beneficiary.query
    if charity_id:
        query = query.filter_by(charity_id=charity_id)
    query = query.order_by(Beneficiary.created_at.desc())
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_b_dict(b) for b in result["items"]]
    return jsonify(result), 200


@beneficiaries_bp.post("/")
@jwt_required()
def create_beneficiary():
    user = current_user()
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if not data.get("full_name"):
        return jsonify({"error": "full_name is required"}), 422

    if user.role == "admin":
        charity_id = data.get("charity_id")
        if not charity_id:
            return jsonify({"error": "charity_id required"}), 422
    else:
        if not user.charity:
            return jsonify({"error": "Charity profile not found"}), 403
        charity_id = user.charity.id

    b = Beneficiary(
        charity_id=charity_id,
        full_name=data["full_name"].strip(),
        age=data.get("age"),
        gender=data.get("gender"),
        location=data.get("location"),
        description=data.get("description"),
        photo_url=data.get("photo_url"),
    )
    db.session.add(b)
    db.session.commit()
    return jsonify(_b_dict(b)), 201


@beneficiaries_bp.get("/<int:ben_id>")
def get_beneficiary(ben_id):
    b = Beneficiary.query.get_or_404(ben_id)
    return jsonify(_b_dict(b)), 200


@beneficiaries_bp.patch("/<int:ben_id>")
@jwt_required()
def update_beneficiary(ben_id):
    b = Beneficiary.query.get_or_404(ben_id)
    user = current_user()
    if user.role == "charity" and (not user.charity or user.charity.id != b.charity_id):
        return jsonify({"error": "Forbidden"}), 403
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    for f in ("full_name", "age", "gender", "location", "description", "photo_url"):
        if f in data:
            setattr(b, f, data[f])
    db.session.commit()
    return jsonify(_b_dict(b)), 200


@beneficiaries_bp.delete("/<int:ben_id>")
@jwt_required()
def delete_beneficiary(ben_id):
    b = Beneficiary.query.get_or_404(ben_id)
    user = current_user()
    if user.role == "charity" and (not user.charity or user.charity.id != b.charity_id):
        return jsonify({"error": "Forbidden"}), 403
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(b)
    db.session.commit()
    return jsonify({"message": "Beneficiary deleted"}), 200


def _b_dict(b: Beneficiary) -> dict:
    return {
        "id":          b.id,
        "charity_id":  b.charity_id,
        "full_name":   b.full_name,
        "age":         b.age,
        "gender":      b.gender,
        "location":    b.location,
        "description": b.description,
        "photo_url":   b.photo_url,
        "created_at":  b.created_at.isoformat() if b.created_at else None,
    }
