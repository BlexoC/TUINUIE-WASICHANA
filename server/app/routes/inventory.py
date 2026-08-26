"""Inventory management API endpoints."""

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.app import db
from app.models import InventoryItem


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
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return _error("page and per_page must be integers.")
    if page < 1 or not 1 <= per_page <= 100:
        return _error("page must be at least 1 and per_page must be between 1 and 100.")

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

    db.session.delete(item)
    db.session.commit()
    return "", 204
