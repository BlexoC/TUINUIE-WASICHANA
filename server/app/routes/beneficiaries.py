"""Beneficiary management API endpoints."""

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.app import db
from app.models import Beneficiary, InventoryDistribution


beneficiaries_bp = Blueprint("beneficiaries", __name__, url_prefix="/api/beneficiaries")

_REQUIRED_FIELDS = {
    "first_name",
    "last_name",
    "date_of_birth",
    "school_name",
    "county",
    "guardian_name",
    "guardian_phone",
}
_OPTIONAL_FIELDS = {"status", "enrolled_at"}
_WRITABLE_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


def _serialize(beneficiary: Beneficiary) -> dict:
    return {
        "id": beneficiary.id,
        "first_name": beneficiary.first_name,
        "last_name": beneficiary.last_name,
        "date_of_birth": beneficiary.date_of_birth.isoformat(),
        "school_name": beneficiary.school_name,
        "county": beneficiary.county,
        "guardian_name": beneficiary.guardian_name,
        "guardian_phone": beneficiary.guardian_phone,
        "status": beneficiary.status,
        "enrolled_at": beneficiary.enrolled_at.isoformat(),
        "created_at": beneficiary.created_at.isoformat(),
    }


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _payload(*, creating: bool) -> tuple[dict | None, tuple | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, _error("Request body must be a JSON object.")

    unknown_fields = set(data) - _WRITABLE_FIELDS
    if unknown_fields:
        return None, _error(f"Unknown field(s): {', '.join(sorted(unknown_fields))}.")

    if creating:
        missing_fields = _REQUIRED_FIELDS - set(data)
        if missing_fields:
            return None, _error(f"Missing required field(s): {', '.join(sorted(missing_fields))}.")
    elif not data:
        return None, _error("Request body must contain at least one writable field.")

    cleaned = dict(data)
    for field in ("date_of_birth", "enrolled_at"):
        if field not in cleaned:
            continue
        if not isinstance(cleaned[field], str):
            return None, _error(f"{field} must use YYYY-MM-DD format.")
        try:
            cleaned[field] = date.fromisoformat(cleaned[field])
        except ValueError:
            return None, _error(f"{field} must use YYYY-MM-DD format.")

    for field in _WRITABLE_FIELDS - {"date_of_birth", "enrolled_at"}:
        if field in cleaned and (not isinstance(cleaned[field], str) or not cleaned[field].strip()):
            return None, _error(f"{field} must be a non-empty string.")
        if field in cleaned:
            cleaned[field] = cleaned[field].strip()

    return cleaned, None


@beneficiaries_bp.post("")
def create_beneficiary():
    """Create a beneficiary."""
    data, error = _payload(creating=True)
    if error:
        return error

    beneficiary = Beneficiary(**data)
    db.session.add(beneficiary)
    db.session.commit()
    return jsonify(_serialize(beneficiary)), 201


@beneficiaries_bp.get("")
def list_beneficiaries():
    """Return beneficiaries in pages, newest records first."""
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return _error("page and per_page must be integers.")
    if page < 1 or not 1 <= per_page <= 100:
        return _error("page must be at least 1 and per_page must be between 1 and 100.")

    statement = select(Beneficiary).order_by(Beneficiary.created_at.desc(), Beneficiary.id.desc())
    page_result = db.paginate(statement, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "beneficiaries": [_serialize(beneficiary) for beneficiary in page_result.items],
            "pagination": {
                "page": page_result.page,
                "per_page": page_result.per_page,
                "total": page_result.total,
                "pages": page_result.pages,
            },
        }
    )


@beneficiaries_bp.put("/<int:beneficiary_id>")
def update_beneficiary(beneficiary_id: int):
    """Update one or more beneficiary fields."""
    beneficiary = db.session.get(Beneficiary, beneficiary_id)
    if beneficiary is None:
        return _error("Beneficiary not found.", 404)

    data, error = _payload(creating=False)
    if error:
        return error
    for field, value in data.items():
        setattr(beneficiary, field, value)
    db.session.commit()
    return jsonify(_serialize(beneficiary))


@beneficiaries_bp.delete("/<int:beneficiary_id>")
def delete_beneficiary(beneficiary_id: int):
    """Delete a beneficiary and their dependent scholarships."""
    beneficiary = db.session.get(Beneficiary, beneficiary_id)
    if beneficiary is None:
        return _error("Beneficiary not found.", 404)
    has_distributions = db.session.scalar(
        select(InventoryDistribution.id)
        .where(InventoryDistribution.beneficiary_id == beneficiary_id)
        .limit(1)
    )
    if has_distributions is not None:
        return _error("Beneficiary cannot be deleted after receiving a distribution.", 409)

    db.session.delete(beneficiary)
    db.session.commit()
    return "", 204
