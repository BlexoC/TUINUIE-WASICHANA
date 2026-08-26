"""Public charity-facing donation views."""

from decimal import Decimal

from flask import Blueprint, jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.app import db
from app.models import Donation


charity_bp = Blueprint("charity", __name__, url_prefix="/api/charity")


def _json_amount(amount: Decimal | None) -> float:
    """Return a JSON-safe monetary amount without exposing Decimal objects."""
    return float(amount or Decimal("0"))


@charity_bp.get("/donations")
def donations():
    """Return public donations and the total raised.

    Donations without a sponsor are anonymous and are included in the total, but
    deliberately omitted from the public donor list.
    """
    total = db.session.scalar(select(func.coalesce(func.sum(Donation.amount), 0)))
    public_donations = db.session.scalars(
        select(Donation)
        .where(Donation.sponsor_id.is_not(None))
        .options(joinedload(Donation.sponsor))
        .order_by(Donation.donated_at.desc(), Donation.id.desc())
    ).all()

    return jsonify(
        {
            "total_donated": _json_amount(total),
            "donations": [
                {
                    "id": donation.id,
                    "donor_name": donation.sponsor.name,
                    "amount": _json_amount(donation.amount),
                    "currency": donation.currency,
                    "donated_at": donation.donated_at.isoformat(),
                }
                for donation in public_donations
            ],
        }
    )
