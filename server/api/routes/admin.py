"""
server/api/routes/admin.py   (all routes require role=admin)

GET    /api/admin/applications                   — list pending applications
GET    /api/admin/applications/<id>              — application detail + documents
POST   /api/admin/applications/<id>/approve      — approve + create Charity record
POST   /api/admin/applications/<id>/reject       — reject with reason
GET    /api/admin/users                          — list all users
PATCH  /api/admin/users/<id>/deactivate          — deactivate a user account
GET    /api/admin/dashboard                      — platform-wide stats
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from server import db
from server.models import (
    User, Charity, CharityApplication, Administrator, Notification, Donor
)
from server.api.middleware.auth import require_role, current_user
from server.utils.pagination import get_pagination_params, paginate

admin_bp = Blueprint("admin", __name__)


def _admin_profile():
    user = current_user()
    return user.administrator


# ---------------------------------------------------------------------------
# GET /api/admin/applications
# ---------------------------------------------------------------------------
@admin_bp.get("/applications")
@jwt_required()
@require_role("admin")
def list_applications():
    status = request.args.get("status", "pending")
    query = CharityApplication.query.filter_by(status=status).order_by(
        CharityApplication.submitted_at.asc()
    )
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_app_summary(a) for a in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/admin/applications/<id>
# ---------------------------------------------------------------------------
@admin_bp.get("/applications/<int:app_id>")
@jwt_required()
@require_role("admin")
def get_application(app_id):
    app_obj = CharityApplication.query.get_or_404(app_id)
    return jsonify(_app_detail(app_obj)), 200


# ---------------------------------------------------------------------------
# POST /api/admin/applications/<id>/approve
# ---------------------------------------------------------------------------
@admin_bp.post("/applications/<int:app_id>/approve")
@jwt_required()
@require_role("admin")
def approve_application(app_id):
    """
    Approve a charity application:
      1. Update application status → approved
      2. Create a Charity row linked to the applicant's User
      3. Notify the applicant

    Idempotent: if already approved, returns 409.
    """
    app_obj = CharityApplication.query.get_or_404(app_id)
    if app_obj.status != "pending":
        return jsonify({"error": f"Application is already {app_obj.status}"}), 409

    admin = _admin_profile()
    if not admin:
        return jsonify({"error": "Admin profile not found"}), 403

    now = datetime.utcnow()
    app_obj.status = "approved"
    app_obj.reviewed_by = admin.id
    app_obj.reviewed_at = now

    # Promote the applicant's role to 'charity' if needed
    applicant = User.query.get(app_obj.applicant_user_id)
    applicant.role = "charity"

    # Create the live Charity record
    charity = Charity(
        user_id=applicant.id,
        application_id=app_obj.id,
        name=app_obj.organization_name,
        description=app_obj.description,
        mission_statement=app_obj.mission_statement,
        registration_number=app_obj.registration_number,
        contact_email=app_obj.contact_email,
        contact_phone=app_obj.contact_phone,
        address=app_obj.address,
        status="active",
    )
    db.session.add(charity)

    # Notify the applicant
    db.session.add(Notification(
        user_id=applicant.id,
        type="application_approved",
        title="Your charity application was approved!",
        message=(
            f"Congratulations! {app_obj.organization_name} is now listed on "
            "the Tuinuie Wasichana platform."
        ),
        related_entity_type="charity_application",
        related_entity_id=app_obj.id,
    ))

    db.session.commit()
    return jsonify({
        "message": "Application approved",
        "charity_id": charity.id,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/admin/applications/<id>/reject
# ---------------------------------------------------------------------------
@admin_bp.post("/applications/<int:app_id>/reject")
@jwt_required()
@require_role("admin")
def reject_application(app_id):
    app_obj = CharityApplication.query.get_or_404(app_id)
    if app_obj.status != "pending":
        return jsonify({"error": f"Application is already {app_obj.status}"}), 409

    data = request.get_json(silent=True) or {}
    reason = data.get("rejection_reason", "").strip()
    if not reason:
        return jsonify({"error": "rejection_reason is required"}), 422

    admin = _admin_profile()
    app_obj.status = "rejected"
    app_obj.reviewed_by = admin.id
    app_obj.reviewed_at = datetime.utcnow()
    app_obj.rejection_reason = reason

    db.session.add(Notification(
        user_id=app_obj.applicant_user_id,
        type="application_rejected",
        title="Charity application not approved",
        message=f"Unfortunately your application was not approved. Reason: {reason}",
        related_entity_type="charity_application",
        related_entity_id=app_obj.id,
    ))
    db.session.commit()
    return jsonify({"message": "Application rejected"}), 200


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------
@admin_bp.get("/users")
@jwt_required()
@require_role("admin")
def list_users():
    role = request.args.get("role")
    is_active = request.args.get("is_active")

    query = User.query
    if role:
        query = query.filter_by(role=role)
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == "true")
    query = query.order_by(User.created_at.desc())

    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_user_summary(u) for u in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/<id>/deactivate
# ---------------------------------------------------------------------------
@admin_bp.patch("/users/<int:user_id>/deactivate")
@jwt_required()
@require_role("admin")
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        return jsonify({"error": "Cannot deactivate an admin account via this endpoint"}), 403
    user.is_active = False
    db.session.commit()
    return jsonify({"message": f"User {user_id} deactivated"}), 200


# ---------------------------------------------------------------------------
# GET /api/admin/dashboard
# ---------------------------------------------------------------------------
@admin_bp.get("/dashboard")
@jwt_required()
@require_role("admin")
def dashboard():
    """Platform-wide aggregate statistics."""
    from sqlalchemy import func
    from server.models import Donation

    total_users     = User.query.count()
    total_charities = Charity.query.filter_by(status="active").count()
    total_donors    = Donor.query.count()
    pending_apps    = CharityApplication.query.filter_by(status="pending").count()

    donation_stats  = db.session.query(
        func.count(Donation.id).label("count"),
        func.coalesce(func.sum(Donation.amount), 0).label("total")
    ).filter(Donation.payment_status == "completed").one()

    return jsonify({
        "total_users":          total_users,
        "total_active_charities": total_charities,
        "total_donors":         total_donors,
        "pending_applications": pending_apps,
        "total_donations":      donation_stats.count,
        "total_amount_raised":  str(donation_stats.total),
    }), 200


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def _app_summary(a: CharityApplication) -> dict:
    return {
        "id":                a.id,
        "organization_name": a.organization_name,
        "contact_email":     a.contact_email,
        "status":            a.status,
        "submitted_at":      a.submitted_at.isoformat() if a.submitted_at else None,
    }


def _app_detail(a: CharityApplication) -> dict:
    return {
        **_app_summary(a),
        "applicant_user_id":  a.applicant_user_id,
        "description":        a.description,
        "mission_statement":  a.mission_statement,
        "registration_number": a.registration_number,
        "contact_phone":      a.contact_phone,
        "address":            a.address,
        "reviewed_by":        a.reviewed_by,
        "reviewed_at":        a.reviewed_at.isoformat() if a.reviewed_at else None,
        "rejection_reason":   a.rejection_reason,
        "documents": [
            {
                "id":            d.id,
                "document_type": d.document_type,
                "file_name":     d.file_name,
                "file_url":      d.file_url,
                "uploaded_at":   d.uploaded_at.isoformat() if d.uploaded_at else None,
            }
            for d in a.documents
        ],
    }


def _user_summary(u: User) -> dict:
    return {
        "id":         u.id,
        "username":   u.username,
        "email":      u.email,
        "role":       u.role,
        "is_active":  u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }
