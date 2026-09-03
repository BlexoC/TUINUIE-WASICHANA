"""
server/api/routes/recurring_plans.py

POST   /api/recurring-plans                 — donor creates a plan
GET    /api/recurring-plans                 — donor's own plans
GET    /api/recurring-plans/<id>            — detail
PATCH  /api/recurring-plans/<id>            — pause / resume / change amount
DELETE /api/recurring-plans/<id>            — cancel plan
"""

from datetime import date, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import (
    RecurringDonationPlan, Charity, CharityProject, PaymentMethod, Notification
)
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

plans_bp = Blueprint("recurring_plans", __name__)

FREQUENCY_DELTAS = {
    "weekly":    timedelta(weeks=1),
    "monthly":   None,       # computed below with month arithmetic
    "quarterly": None,
    "yearly":    None,
}


def _next_date(frequency: str, from_date: date) -> date:
    """Calculate the next donation date from a given base date."""
    if frequency == "weekly":
        return from_date + timedelta(weeks=1)
    if frequency == "monthly":
        m = from_date.month + 1
        y = from_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        d = min(from_date.day, [31,28,31,30,31,30,31,31,30,31,30,31][m-1])
        return date(y, m, d)
    if frequency == "quarterly":
        m = from_date.month + 3
        y = from_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        return date(y, m, min(from_date.day, 28))
    if frequency == "yearly":
        return date(from_date.year + 1, from_date.month, from_date.day)
    raise ValueError(f"Unknown frequency: {frequency}")


# ---------------------------------------------------------------------------
# POST /api/recurring-plans
# ---------------------------------------------------------------------------
@plans_bp.post("/")
@jwt_required()
def create_plan():
    """
    Set up a new recurring donation plan.

    Body (JSON):
        charity_id          int      required
        payment_method_id   int      required
        amount              decimal  required
        frequency           str      "weekly"|"monthly"|"quarterly"|"yearly"
        project_id          int      optional
        currency            str      default "USD"
        is_anonymous        bool     optional
        day_of_month        int      1-31, optional
    """
    user = current_user()
    if user.role != "donor" or not user.donor:
        return jsonify({"error": "Donor profile required"}), 403
    donor = user.donor

    data = request.get_json(silent=True) or {}
    required = ("charity_id", "payment_method_id", "amount", "frequency")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    charity = Charity.query.get(data["charity_id"])
    if not charity or charity.status != "active":
        return jsonify({"error": "Charity not found or inactive"}), 404

    pm = PaymentMethod.query.filter_by(id=data["payment_method_id"], donor_id=donor.id).first()
    if not pm:
        return jsonify({"error": "Payment method not found or does not belong to you"}), 404

    if data["frequency"] not in ("weekly", "monthly", "quarterly", "yearly"):
        return jsonify({"error": "Invalid frequency value"}), 422

    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive number"}), 422

    project_id = data.get("project_id")
    if project_id:
        project = CharityProject.query.get(project_id)
        if not project or project.charity_id != charity.id:
            return jsonify({"error": "Project not found or does not belong to charity"}), 404

    today = date.today()
    plan = RecurringDonationPlan(
        donor_id=donor.id,
        charity_id=charity.id,
        project_id=project_id,
        payment_method_id=pm.id,
        amount=amount,
        currency=data.get("currency", "USD").upper(),
        frequency=data["frequency"],
        day_of_month=data.get("day_of_month"),
        start_date=today,
        next_donation_date=_next_date(data["frequency"], today),
        status="active",
        is_anonymous=data.get("is_anonymous", donor.default_anonymous),
    )
    db.session.add(plan)
    db.session.flush()

    # Notify the donor
    db.session.add(Notification(
        user_id=user.id,
        type="donation_successful",
        title="Recurring plan created",
        message=(
            f"Your {data['frequency']} donation of "
            f"{plan.currency} {amount} to {charity.name} has been set up."
        ),
        related_entity_type="recurring_plan",
        related_entity_id=plan.id,
    ))
    db.session.commit()
    return jsonify(_plan_dict(plan)), 201


# ---------------------------------------------------------------------------
# GET /api/recurring-plans
# ---------------------------------------------------------------------------
@plans_bp.get("/")
@jwt_required()
def list_plans():
    user = current_user()
    if user.role != "donor" or not user.donor:
        return jsonify({"error": "Donor profile required"}), 403

    status = request.args.get("status")
    query = RecurringDonationPlan.query.filter_by(donor_id=user.donor.id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(RecurringDonationPlan.created_at.desc())

    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_plan_dict(p) for p in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/recurring-plans/<id>
# ---------------------------------------------------------------------------
@plans_bp.get("/<int:plan_id>")
@jwt_required()
def get_plan(plan_id):
    user = current_user()
    plan = RecurringDonationPlan.query.get_or_404(plan_id)

    if user.role == "donor" and plan.donor_id != user.donor.id:
        return jsonify({"error": "Forbidden"}), 403
    if user.role not in ("donor", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(_plan_dict(plan)), 200


# ---------------------------------------------------------------------------
# PATCH /api/recurring-plans/<id>
# ---------------------------------------------------------------------------
@plans_bp.patch("/<int:plan_id>")
@jwt_required()
def update_plan(plan_id):
    """
    Donors may pause/resume their own plans or change the amount.
    Admins may change any field.

    Cancellation goes through DELETE /api/recurring-plans/<id>.
    """
    user = current_user()
    plan = RecurringDonationPlan.query.get_or_404(plan_id)

    if user.role == "donor":
        if not user.donor or plan.donor_id != user.donor.id:
            return jsonify({"error": "Forbidden"}), 403
    elif user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}

    if "status" in data:
        allowed = ("active", "paused") if user.role == "donor" else ("active", "paused", "cancelled")
        if data["status"] not in allowed:
            return jsonify({"error": f"Allowed status values: {allowed}"}), 422
        plan.status = data["status"]

    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
            plan.amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "amount must be a positive number"}), 422

    if "is_anonymous" in data:
        plan.is_anonymous = bool(data["is_anonymous"])

    db.session.commit()
    return jsonify(_plan_dict(plan)), 200


# ---------------------------------------------------------------------------
# DELETE /api/recurring-plans/<id>  — cancel
# ---------------------------------------------------------------------------
@plans_bp.delete("/<int:plan_id>")
@jwt_required()
def cancel_plan(plan_id):
    user = current_user()
    plan = RecurringDonationPlan.query.get_or_404(plan_id)

    if user.role == "donor":
        if not user.donor or plan.donor_id != user.donor.id:
            return jsonify({"error": "Forbidden"}), 403
    elif user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    if plan.status == "cancelled":
        return jsonify({"error": "Plan is already cancelled"}), 409

    plan.status = "cancelled"
    db.session.commit()
    return jsonify({"message": "Recurring plan cancelled", "plan_id": plan_id}), 200


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------
def _plan_dict(p: RecurringDonationPlan) -> dict:
    return {
        "id":                 p.id,
        "donor_id":           p.donor_id,
        "charity_id":         p.charity_id,
        "project_id":         p.project_id,
        "payment_method_id":  p.payment_method_id,
        "amount":             str(p.amount),
        "currency":           p.currency,
        "frequency":          p.frequency,
        "day_of_month":       p.day_of_month,
        "start_date":         p.start_date.isoformat() if p.start_date else None,
        "next_donation_date": p.next_donation_date.isoformat() if p.next_donation_date else None,
        "status":             p.status,
        "is_anonymous":       p.is_anonymous,
        "created_at":         p.created_at.isoformat() if p.created_at else None,
    }
