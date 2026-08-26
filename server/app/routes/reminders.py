from flask import Blueprint, request, jsonify
from datetime import datetime

from ..app import db
try:
    from ..models import Reminder
except Exception:
    Reminder = None

bp = Blueprint("reminders", __name__, url_prefix="/api/reminders")


def _parse_iso(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


@bp.route("", methods=["POST"])
def create_reminder():
    data = request.get_json() or {}
    donor_id = data.get("donor_id")
    if donor_id is None:
        return jsonify({"error": "donor_id is required"}), 400

    if Reminder is None:
        return jsonify({"error": "Reminder model not available"}), 501

    reminder = Reminder(
        donor_id=donor_id,
        amount=data.get("amount"),
        currency=data.get("currency") or "USD",
        interval=data.get("interval"),
        next_date=_parse_iso(data.get("next_date")),
        note=data.get("note"),
        active=data.get("active", True),
    )
    db.session.add(reminder)
    db.session.commit()

    return jsonify(reminder.to_dict()), 201


@bp.route("", methods=["GET"])
def list_reminders():
    if Reminder is None:
        return jsonify({"error": "Reminder model not available"}), 501

    donor_id = request.args.get("donor_id", type=int)
    q = Reminder.query
    if donor_id:
        q = q.filter_by(donor_id=donor_id)
    reminders = q.filter_by(active=True).all()
    return jsonify([r.to_dict() for r in reminders])


@bp.route("/<int:reminder_id>", methods=["PUT"])
def update_reminder(reminder_id):
    if Reminder is None:
        return jsonify({"error": "Reminder model not available"}), 501

    reminder = Reminder.query.get_or_404(reminder_id)
    data = request.get_json() or {}

    # Optional donor ownership check: if donor_id provided, require match
    if "donor_id" in data and data.get("donor_id") != reminder.donor_id:
        return jsonify({"error": "donor_id mismatch"}), 403

    if "amount" in data:
        reminder.amount = data.get("amount")
    if "currency" in data:
        reminder.currency = data.get("currency")
    if "interval" in data:
        reminder.interval = data.get("interval")
    if "next_date" in data:
        reminder.next_date = _parse_iso(data.get("next_date"))
    if "note" in data:
        reminder.note = data.get("note")
    if "active" in data:
        reminder.active = bool(data.get("active"))

    db.session.commit()
    return jsonify(reminder.to_dict())


@bp.route("/<int:reminder_id>", methods=["DELETE"])
def delete_reminder(reminder_id):
    if Reminder is None:
        return jsonify({"error": "Reminder model not available"}), 501

    reminder = Reminder.query.get_or_404(reminder_id)
    # perform hard delete
    db.session.delete(reminder)
    db.session.commit()
    return "", 204
