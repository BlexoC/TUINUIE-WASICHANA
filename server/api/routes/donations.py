"""
server/api/routes/donations.py

POST   /api/donations                          — donor makes a one-time donation
GET    /api/donations                          — donor's own donation history
GET    /api/donations/<id>                     — detail (donor/charity/admin)
GET    /api/donations/charity/<charity_id>     — charity's received donations
POST   /api/donations/<id>/refund              — admin-only refund flag
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from server import db
from server.models import Donation, Donor, Charity, CharityProject, Notification
from server.api.middleware.auth import current_user, require_role
from server.utils.pagination import get_pagination_params, paginate

donations_bp = Blueprint("donations", __name__)


# ---------------------------------------------------------------------------
# POST /api/donations
# ---------------------------------------------------------------------------
@donations_bp.post("/")
@jwt_required()
def create_donation():
    """
    Record a completed one-time donation from a donor.

    In production the payment charge happens client-side (Stripe.js) and
    the resulting provider_transaction_id is posted here for idempotent
    recording.  We never touch raw card numbers.

    Body (JSON):
        charity_id              int      required
        amount                  decimal  required
        currency                str      default "USD"
        payment_provider        str      "stripe"|"paypal"
        provider_transaction_id str      required (from payment gateway)
        project_id              int      optional
        is_anonymous            bool     optional (overrides donor's default)
    """
    user = current_user()
    if user.role != "donor" or not user.donor:
        return jsonify({"error": "Donor profile required"}), 403

    data = request.get_json(silent=True) or {}
    required = ("charity_id", "amount", "payment_provider", "provider_transaction_id")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    charity = Charity.query.get(data["charity_id"])
    if not charity or charity.status != "active":
        return jsonify({"error": "Charity not found or inactive"}), 404

    if data["payment_provider"] not in ("stripe", "paypal"):
        return jsonify({"error": "payment_provider must be 'stripe' or 'paypal'"}), 422

    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive number"}), 422

    # Idempotency: if the transaction was already recorded, return it
    existing = Donation.query.filter_by(
        payment_provider=data["payment_provider"],
        provider_transaction_id=data["provider_transaction_id"]
    ).first()
    if existing:
        return jsonify(_donation_dict(existing)), 200

    project_id = data.get("project_id")
    if project_id:
        project = CharityProject.query.get(project_id)
        if not project or project.charity_id != charity.id:
            return jsonify({"error": "Project not found or does not belong to charity"}), 404

    donor = user.donor
    is_anonymous = data.get("is_anonymous", donor.default_anonymous)

    donation = Donation(
        donor_id=donor.id,
        charity_id=charity.id,
        project_id=project_id,
        donation_type="one_time",
        amount=amount,
        currency=data.get("currency", "USD").upper(),
        is_anonymous=is_anonymous,
        payment_provider=data["payment_provider"],
        provider_transaction_id=data["provider_transaction_id"],
        payment_status="completed",   # payment already charged by gateway
    )
    db.session.add(donation)
    db.session.flush()

    # Fire in-app notification for the donor
    db.session.add(Notification(
        user_id=user.id,
        type="donation_successful",
        title="Donation confirmed",
        message=f"Your donation of {donation.currency} {amount} to {charity.name} was received.",
        related_entity_type="donation",
        related_entity_id=donation.id,
    ))

    db.session.commit()
    return jsonify(_donation_dict(donation)), 201


# ---------------------------------------------------------------------------
# GET /api/donations  — donor's own history
# ---------------------------------------------------------------------------
@donations_bp.get("/")
@jwt_required()
def list_my_donations():
    user = current_user()
    if user.role != "donor" or not user.donor:
        return jsonify({"error": "Donor profile required"}), 403

    query = Donation.query.filter_by(donor_id=user.donor.id).order_by(Donation.donated_at.desc())
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_donation_dict(d) for d in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/donations/<id>
# ---------------------------------------------------------------------------
@donations_bp.get("/<int:donation_id>")
@jwt_required()
def get_donation(donation_id):
    user = current_user()
    donation = Donation.query.get_or_404(donation_id)

    # Access control: donor sees their own; charity sees received; admin sees all
    if user.role == "donor" and donation.donor_id != user.donor.id:
        return jsonify({"error": "Forbidden"}), 403
    if user.role == "charity" and donation.charity_id != user.charity.id:
        return jsonify({"error": "Forbidden"}), 403

    viewer = "self" if user.role == "donor" else user.role
    return jsonify(_donation_dict(donation, viewer_role=viewer)), 200


# ---------------------------------------------------------------------------
# GET /api/donations/charity/<charity_id>  — charity's received donations
# ---------------------------------------------------------------------------
@donations_bp.get("/charity/<int:charity_id>")
@jwt_required()
def charity_donations(charity_id):
    user = current_user()

    if user.role == "charity":
        if not user.charity or user.charity.id != charity_id:
            return jsonify({"error": "Forbidden"}), 403
    elif user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    query = Donation.query.filter_by(charity_id=charity_id).order_by(Donation.donated_at.desc())
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    # Charity view — mask anonymous donors
    result["items"] = [_donation_dict(d, viewer_role="charity") for d in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/donations/<id>/refund  — admin only
# ---------------------------------------------------------------------------
@donations_bp.post("/<int:donation_id>/refund")
@jwt_required()
@require_role("admin")
def refund_donation(donation_id):
    """
    Mark a donation as refunded.
    Actual gateway refund must be triggered separately via Stripe/PayPal API.
    """
    donation = Donation.query.get_or_404(donation_id)
    if donation.payment_status == "refunded":
        return jsonify({"error": "Already refunded"}), 409
    if donation.payment_status != "completed":
        return jsonify({"error": "Only completed donations can be refunded"}), 422

    donation.payment_status = "refunded"
    db.session.commit()
    return jsonify({"message": "Donation marked as refunded", "donation_id": donation_id}), 200


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------
def _donation_dict(d: Donation, viewer_role: str = "self") -> dict:
    base = {
        "id":                      d.id,
        "charity_id":              d.charity_id,
        "project_id":              d.project_id,
        "recurring_plan_id":       d.recurring_plan_id,
        "donation_type":           d.donation_type,
        "amount":                  str(d.amount),
        "currency":                d.currency,
        "is_anonymous":            d.is_anonymous,
        "payment_provider":        d.payment_provider,
        "provider_transaction_id": d.provider_transaction_id,
        "payment_status":          d.payment_status,
        "donated_at":              d.donated_at.isoformat() if d.donated_at else None,
    }
    # Mask identity for charity view of anonymous donations
    if d.is_anonymous and viewer_role == "charity":
        base["donor_id"] = None
    else:
        base["donor_id"] = d.donor_id
    return base
