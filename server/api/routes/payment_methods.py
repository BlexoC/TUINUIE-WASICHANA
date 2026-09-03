"""
server/api/routes/payment_methods.py

GET    /api/payment-methods              — list donor's saved methods
POST   /api/payment-methods             — add a new saved method (tokenized)
DELETE /api/payment-methods/<id>        — remove a saved method
PATCH  /api/payment-methods/<id>/default — set as default
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import PaymentMethod
from server.api.middleware.auth import current_user

payment_methods_bp = Blueprint("payment_methods", __name__)


@payment_methods_bp.get("/")
@jwt_required()
def list_methods():
    user = current_user()
    if not user.donor:
        return jsonify({"error": "Donor profile required"}), 403
    methods = PaymentMethod.query.filter_by(donor_id=user.donor.id).all()
    return jsonify([_pm_dict(m) for m in methods]), 200


@payment_methods_bp.post("/")
@jwt_required()
def add_method():
    """
    Save a tokenized payment method returned by Stripe.js / PayPal SDK.
    Never pass raw card data through this endpoint.

    Body:
        provider                  "stripe"|"paypal"
        provider_customer_id      str   (e.g. Stripe cus_xxx)
        provider_payment_method_id str  (e.g. Stripe pm_xxx)
        is_default                bool  optional
    """
    user = current_user()
    if not user.donor:
        return jsonify({"error": "Donor profile required"}), 403

    data = request.get_json(silent=True) or {}
    required = ("provider", "provider_customer_id", "provider_payment_method_id")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    if data["provider"] not in ("stripe", "paypal"):
        return jsonify({"error": "provider must be 'stripe' or 'paypal'"}), 422

    # Prevent duplicate
    if PaymentMethod.query.filter_by(
        provider=data["provider"],
        provider_payment_method_id=data["provider_payment_method_id"]
    ).first():
        return jsonify({"error": "This payment method is already saved"}), 409

    donor = user.donor
    is_default = bool(data.get("is_default", False))

    # If setting as default, clear existing defaults
    if is_default:
        PaymentMethod.query.filter_by(donor_id=donor.id, is_default=True).update({"is_default": False})

    pm = PaymentMethod(
        donor_id=donor.id,
        provider=data["provider"],
        provider_customer_id=data["provider_customer_id"],
        provider_payment_method_id=data["provider_payment_method_id"],
        is_default=is_default,
    )
    db.session.add(pm)
    db.session.commit()
    return jsonify(_pm_dict(pm)), 201


@payment_methods_bp.delete("/<int:pm_id>")
@jwt_required()
def delete_method(pm_id):
    user = current_user()
    pm = PaymentMethod.query.get_or_404(pm_id)
    if not user.donor or pm.donor_id != user.donor.id:
        return jsonify({"error": "Forbidden"}), 403

    # Prevent deletion if active recurring plans depend on this method
    from server.models import RecurringDonationPlan
    active = RecurringDonationPlan.query.filter_by(
        payment_method_id=pm.id, status="active"
    ).count()
    if active:
        return jsonify({
            "error": "Cannot delete: this payment method is used by active recurring plans",
            "active_plans": active,
        }), 409

    db.session.delete(pm)
    db.session.commit()
    return jsonify({"message": "Payment method removed"}), 200


@payment_methods_bp.patch("/<int:pm_id>/default")
@jwt_required()
def set_default(pm_id):
    user = current_user()
    pm = PaymentMethod.query.get_or_404(pm_id)
    if not user.donor or pm.donor_id != user.donor.id:
        return jsonify({"error": "Forbidden"}), 403

    PaymentMethod.query.filter_by(donor_id=user.donor.id, is_default=True).update({"is_default": False})
    pm.is_default = True
    db.session.commit()
    return jsonify({"message": "Default payment method updated"}), 200


def _pm_dict(m: PaymentMethod) -> dict:
    return {
        "id":                         m.id,
        "provider":                   m.provider,
        "provider_customer_id":       m.provider_customer_id,
        "provider_payment_method_id": m.provider_payment_method_id,
        "is_default":                 m.is_default,
        "created_at":                 m.created_at.isoformat() if m.created_at else None,
    }
