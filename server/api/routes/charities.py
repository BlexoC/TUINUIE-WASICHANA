"""
server/api/routes/charities.py

GET    /api/charities               — public list with search & filter
GET    /api/charities/<id>          — public detail
PATCH  /api/charities/<id>          — charity owner or admin update
POST   /api/charities/apply         — submit a charity application (authenticated user)
GET    /api/charities/<id>/stats    — donation stats (public)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import or_

from server import db
from server.models import User, CharityApplication, ApplicationDocument, Charity
from server.api.middleware.auth import require_role, current_user
from server.utils.pagination import get_pagination_params, paginate

charities_bp = Blueprint("charities", __name__)


# ---------------------------------------------------------------------------
# GET /api/charities
# ---------------------------------------------------------------------------
@charities_bp.get("/")
def list_charities():
    """
    Public paginated list of active charities.
    Query params: ?search=<str>&status=active|suspended&page=1&per_page=20
    """
    q = request.args.get("search", "").strip()
    status = request.args.get("status", "active")

    query = Charity.query.filter(Charity.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Charity.name.ilike(like), Charity.description.ilike(like))
        )
    query = query.order_by(Charity.name)

    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_charity_summary(c) for c in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/charities/<id>
# ---------------------------------------------------------------------------
@charities_bp.get("/<int:charity_id>")
def get_charity(charity_id):
    charity = Charity.query.get_or_404(charity_id)
    return jsonify(_charity_detail(charity)), 200


# ---------------------------------------------------------------------------
# GET /api/charities/<id>/stats
# ---------------------------------------------------------------------------
@charities_bp.get("/<int:charity_id>/stats")
def charity_stats(charity_id):
    """Return aggregate donation stats for a charity's detail page."""
    charity = Charity.query.get_or_404(charity_id)
    from server.models import Donation
    from sqlalchemy import func
    row = db.session.query(
        func.count(Donation.id).label("total_donations"),
        func.coalesce(func.sum(Donation.amount), 0).label("total_raised"),
        func.count(func.distinct(Donation.donor_id)).label("unique_donors"),
    ).filter(
        Donation.charity_id == charity_id,
        Donation.payment_status == "completed"
    ).one()
    return jsonify({
        "charity_id":      charity_id,
        "total_donations": row.total_donations,
        "total_raised":    str(row.total_raised),
        "unique_donors":   row.unique_donors,
    }), 200


# ---------------------------------------------------------------------------
# PATCH /api/charities/<id>
# ---------------------------------------------------------------------------
@charities_bp.patch("/<int:charity_id>")
@jwt_required()
def update_charity(charity_id):
    """
    Update a charity's public profile.
    Charity owner can update their own record.
    Admin can update any charity and toggle status.
    """
    user = current_user()
    charity = Charity.query.get_or_404(charity_id)

    # Ownership check
    if user.role == "charity" and charity.user_id != user.id:
        return jsonify({"error": "You do not own this charity"}), 403
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}

    updatable = [
        "name", "description", "mission_statement", "logo_url",
        "website_url", "contact_email", "contact_phone", "address",
    ]
    for field in updatable:
        if field in data:
            setattr(charity, field, data[field])

    # Only admins may flip status
    if user.role == "admin" and "status" in data:
        if data["status"] not in ("active", "suspended"):
            return jsonify({"error": "Invalid status value"}), 422
        charity.status = data["status"]

    db.session.commit()
    return jsonify(_charity_detail(charity)), 200


# ---------------------------------------------------------------------------
# POST /api/charities/apply
# ---------------------------------------------------------------------------
@charities_bp.post("/apply")
@jwt_required()
def apply():
    """
    Submit a new charity application.
    The requesting user must have role='charity' (set at registration).
    A user may only have one pending application at a time.
    """
    user = current_user()
    if user.role != "charity":
        return jsonify({"error": "Only users with role 'charity' may apply"}), 403

    # Reject if they already have a charity (approved)
    if user.charity:
        return jsonify({"error": "You already have an approved charity"}), 409

    # Reject if a pending application already exists
    existing = CharityApplication.query.filter_by(
        applicant_user_id=user.id, status="pending"
    ).first()
    if existing:
        return jsonify({"error": "You already have a pending application", "application_id": existing.id}), 409

    data = request.get_json(silent=True) or {}
    required = ("organization_name", "contact_email")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    app_obj = CharityApplication(
        applicant_user_id=user.id,
        organization_name=data["organization_name"].strip(),
        description=data.get("description"),
        mission_statement=data.get("mission_statement"),
        registration_number=data.get("registration_number"),
        contact_email=data["contact_email"].strip().lower(),
        contact_phone=data.get("contact_phone"),
        address=data.get("address"),
    )
    db.session.add(app_obj)
    db.session.flush()

    # Attach documents if provided as [{"document_type": ..., "file_url": ..., ...}]
    for doc in data.get("documents", []):
        if not doc.get("document_type") or not doc.get("file_url"):
            continue
        db.session.add(ApplicationDocument(
            application_id=app_obj.id,
            document_type=doc["document_type"],
            file_name=doc.get("file_name", "document"),
            file_url=doc["file_url"],
            mime_type=doc.get("mime_type"),
            file_size_bytes=doc.get("file_size_bytes"),
        ))

    db.session.commit()
    return jsonify({
        "message": "Application submitted successfully",
        "application_id": app_obj.id,
    }), 201


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def _charity_summary(c: Charity) -> dict:
    return {
        "id":          c.id,
        "name":        c.name,
        "description": c.description,
        "logo_url":    c.logo_url,
        "status":      c.status,
    }


def _charity_detail(c: Charity) -> dict:
    return {
        "id":                  c.id,
        "name":                c.name,
        "description":         c.description,
        "mission_statement":   c.mission_statement,
        "logo_url":            c.logo_url,
        "website_url":         c.website_url,
        "registration_number": c.registration_number,
        "contact_email":       c.contact_email,
        "contact_phone":       c.contact_phone,
        "address":             c.address,
        "status":              c.status,
        "created_at":          c.created_at.isoformat() if c.created_at else None,
        "updated_at":          c.updated_at.isoformat() if c.updated_at else None,
    }
