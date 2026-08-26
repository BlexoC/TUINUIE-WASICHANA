"""Inventory management and distribution API endpoints."""

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from app.app import db
from app.models import Beneficiary, InventoryDistribution, InventoryItem, utc_now


inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")

_REQUIRED_FIELDS = {"name", "quantity"}
_OPTIONAL_FIELDS = {"unit", "category", "description"}
_WRITABLE_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


def _serialize(item: InventoryItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "category": item.category,
        "description": item.description,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _pagination():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return None, _error("page and per_page must be integers.")
    if page < 1 or not 1 <= per_page <= 100:
        return None, _error("page must be at least 1 and per_page must be between 1 and 100.")
    return (page, per_page), None


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
    if "quantity" in cleaned and (
        isinstance(cleaned["quantity"], bool)
        or not isinstance(cleaned["quantity"], int)
        or cleaned["quantity"] < 0
    ):
        return None, _error("quantity must be a non-negative integer.")

    for field in ("name", "unit", "category"):
        if field in cleaned:
            if not isinstance(cleaned[field], str) or not cleaned[field].strip():
                return None, _error(f"{field} must be a non-empty string.")
            cleaned[field] = cleaned[field].strip()

    if "description" in cleaned and cleaned["description"] is not None:
        if not isinstance(cleaned["description"], str):
            return None, _error("description must be a string or null.")
        cleaned["description"] = cleaned["description"].strip() or None

    return cleaned, None


@inventory_bp.post("")
def create_inventory_item():
    """Create an inventory item."""
    data, error = _payload(creating=True)
    if error:
        return error

    item = InventoryItem(**data)
    db.session.add(item)
    db.session.commit()
    return jsonify(_serialize(item)), 201


@inventory_bp.get("")
def list_inventory():
    """Return inventory items in pages, newest records first."""
    pagination, error = _pagination()
    if error:
        return error
    page, per_page = pagination

    statement = select(InventoryItem).order_by(InventoryItem.created_at.desc(), InventoryItem.id.desc())
    page_result = db.paginate(statement, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "inventory": [_serialize(item) for item in page_result.items],
            "pagination": {
                "page": page_result.page,
                "per_page": page_result.per_page,
                "total": page_result.total,
                "pages": page_result.pages,
            },
        }
    )


@inventory_bp.put("/<int:item_id>")
def update_inventory_item(item_id: int):
    """Update one or more inventory item fields."""
    item = db.session.get(InventoryItem, item_id)
    if item is None:
        return _error("Inventory item not found.", 404)

    data, error = _payload(creating=False)
    if error:
        return error
    for field, value in data.items():
        setattr(item, field, value)
    db.session.commit()
    return jsonify(_serialize(item))


@inventory_bp.delete("/<int:item_id>")
def delete_inventory_item(item_id: int):
    """Delete an inventory item."""
    item = db.session.get(InventoryItem, item_id)
    if item is None:
        return _error("Inventory item not found.", 404)
    has_distributions = db.session.scalar(
        select(InventoryDistribution.id)
        .where(InventoryDistribution.inventory_item_id == item_id)
        .limit(1)
    )
    if has_distributions is not None:
        return _error("Inventory item cannot be deleted after distribution.", 409)

    db.session.delete(item)
    db.session.commit()
    return "", 204


def _distribution_payload() -> tuple[dict | None, tuple | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, _error("Request body must be a JSON object.")

    # inventory_id is accepted as a concise client-facing alias.
    if "inventory_id" in data:
        if "inventory_item_id" in data:
            return None, _error("Provide inventory_item_id or inventory_id, not both.")
        data = {**data, "inventory_item_id": data["inventory_id"]}
        del data["inventory_id"]

    writable_fields = {"inventory_item_id", "beneficiary_id", "quantity", "distributed_at", "notes"}
    unknown_fields = set(data) - writable_fields
    if unknown_fields:
        return None, _error(f"Unknown field(s): {', '.join(sorted(unknown_fields))}.")
    required_fields = {"inventory_item_id", "beneficiary_id", "quantity"}
    missing_fields = required_fields - set(data)
    if missing_fields:
        return None, _error(f"Missing required field(s): {', '.join(sorted(missing_fields))}.")

    cleaned = dict(data)
    for field in ("inventory_item_id", "beneficiary_id", "quantity"):
        value = cleaned[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return None, _error(f"{field} must be a positive integer.")
    if "distributed_at" in cleaned:
        if not isinstance(cleaned["distributed_at"], str):
            return None, _error("distributed_at must use YYYY-MM-DD format.")
        try:
            cleaned["distributed_at"] = date.fromisoformat(cleaned["distributed_at"])
        except ValueError:
            return None, _error("distributed_at must use YYYY-MM-DD format.")
    if "notes" in cleaned and cleaned["notes"] is not None:
        if not isinstance(cleaned["notes"], str):
            return None, _error("notes must be a string or null.")
        cleaned["notes"] = cleaned["notes"].strip() or None
    return cleaned, None


def _serialize_distribution(distribution: InventoryDistribution) -> dict:
    beneficiary = distribution.beneficiary
    item = distribution.inventory_item
    return {
        "id": distribution.id,
        "inventory_item_id": distribution.inventory_item_id,
        "inventory_item_name": item.name,
        "beneficiary_id": distribution.beneficiary_id,
        "beneficiary_name": f"{beneficiary.first_name} {beneficiary.last_name}",
        "quantity": distribution.quantity,
        "unit": item.unit,
        "distributed_at": distribution.distributed_at.isoformat(),
        "notes": distribution.notes,
        "created_at": distribution.created_at.isoformat(),
    }


@inventory_bp.post("/distribute")
def distribute_inventory():
    """Record a distribution and deduct its quantity from the item stock."""
    data, error = _distribution_payload()
    if error:
        return error

    item = db.session.get(InventoryItem, data["inventory_item_id"])
    if item is None:
        return _error("Inventory item not found.", 404)
    beneficiary = db.session.get(Beneficiary, data["beneficiary_id"])
    if beneficiary is None:
        return _error("Beneficiary not found.", 404)

    stock_update = db.session.execute(
        update(InventoryItem)
        .where(
            InventoryItem.id == item.id,
            InventoryItem.quantity >= data["quantity"],
        )
        .values(quantity=InventoryItem.quantity - data["quantity"], updated_at=utc_now())
    )
    if stock_update.rowcount != 1:
        db.session.rollback()
        return _error("Insufficient inventory quantity.", 409)

    distribution = InventoryDistribution(**data)
    db.session.add(distribution)
    db.session.commit()
    distribution = db.session.scalar(
        select(InventoryDistribution)
        .where(InventoryDistribution.id == distribution.id)
        .options(
            joinedload(InventoryDistribution.inventory_item),
            joinedload(InventoryDistribution.beneficiary),
        )
    )
    return jsonify(_serialize_distribution(distribution)), 201


@inventory_bp.get("/distributions")
def list_distributions():
    """Return distribution history in pages, newest distributions first."""
    pagination, error = _pagination()
    if error:
        return error
    page, per_page = pagination
    statement = (
        select(InventoryDistribution)
        .options(
            joinedload(InventoryDistribution.inventory_item),
            joinedload(InventoryDistribution.beneficiary),
        )
        .order_by(InventoryDistribution.distributed_at.desc(), InventoryDistribution.id.desc())
    )
    page_result = db.paginate(statement, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "distributions": [_serialize_distribution(item) for item in page_result.items],
            "pagination": {
                "page": page_result.page,
                "per_page": page_result.per_page,
                "total": page_result.total,
                "pages": page_result.pages,
            },
        }
    )
