"""
server/api/routes/inventory.py

GET    /api/inventory?charity_id=              — list items
POST   /api/inventory                          — add item
GET    /api/inventory/<id>                     — detail + distribution log
PATCH  /api/inventory/<id>                     — update quantity / meta
DELETE /api/inventory/<id>                     — delete item
POST   /api/inventory/<id>/distribute          — record a distribution
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import InventoryItem, InventoryDistribution, Beneficiary
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

inventory_bp = Blueprint("inventory", __name__)


def _charity_owns_item(user, item: InventoryItem):
    if user.role == "admin":
        return True
    return user.role == "charity" and user.charity and user.charity.id == item.charity_id


@inventory_bp.get("/")
@jwt_required()
def list_items():
    user = current_user()
    charity_id = request.args.get("charity_id", type=int)

    query = InventoryItem.query
    if user.role == "charity":
        # Charity may only see their own inventory
        if not user.charity:
            return jsonify({"error": "Charity profile not found"}), 403
        query = query.filter_by(charity_id=user.charity.id)
    elif charity_id:
        query = query.filter_by(charity_id=charity_id)

    query = query.order_by(InventoryItem.item_name)
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_item_dict(i) for i in result["items"]]
    return jsonify(result), 200


@inventory_bp.post("/")
@jwt_required()
def create_item():
    user = current_user()
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if not data.get("item_name"):
        return jsonify({"error": "item_name is required"}), 422

    charity_id = data.get("charity_id") if user.role == "admin" else (user.charity.id if user.charity else None)
    if not charity_id:
        return jsonify({"error": "charity_id required"}), 422

    item = InventoryItem(
        charity_id=charity_id,
        item_name=data["item_name"].strip(),
        category=data.get("category"),
        unit=data.get("unit"),
        quantity_available=max(0, int(data.get("quantity_available", 0))),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(_item_dict(item)), 201


@inventory_bp.get("/<int:item_id>")
@jwt_required()
def get_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    user = current_user()
    if not _charity_owns_item(user, item):
        return jsonify({"error": "Forbidden"}), 403

    distributions = InventoryDistribution.query.filter_by(inventory_item_id=item_id)\
        .order_by(InventoryDistribution.distributed_at.desc()).limit(50).all()
    d = _item_dict(item)
    d["recent_distributions"] = [_dist_dict(dist) for dist in distributions]
    return jsonify(d), 200


@inventory_bp.patch("/<int:item_id>")
@jwt_required()
def update_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    user = current_user()
    if not _charity_owns_item(user, item):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    for f in ("item_name", "category", "unit"):
        if f in data:
            setattr(item, f, data[f])
    if "quantity_available" in data:
        qty = int(data["quantity_available"])
        if qty < 0:
            return jsonify({"error": "quantity_available cannot be negative"}), 422
        item.quantity_available = qty

    db.session.commit()
    return jsonify(_item_dict(item)), 200


@inventory_bp.delete("/<int:item_id>")
@jwt_required()
def delete_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    user = current_user()
    if not _charity_owns_item(user, item):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted"}), 200


@inventory_bp.post("/<int:item_id>/distribute")
@jwt_required()
def distribute(item_id):
    """
    Record that a quantity of this item was distributed to a beneficiary.
    Atomically decrements quantity_available and inserts the distribution log.
    """
    item = InventoryItem.query.get_or_404(item_id)
    user = current_user()
    if not _charity_owns_item(user, item):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    ben_id = data.get("beneficiary_id")
    qty    = data.get("quantity")

    if not ben_id or not qty:
        return jsonify({"error": "beneficiary_id and quantity are required"}), 422

    try:
        qty = int(qty)
        if qty <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "quantity must be a positive integer"}), 422

    beneficiary = Beneficiary.query.get(ben_id)
    if not beneficiary or beneficiary.charity_id != item.charity_id:
        return jsonify({"error": "Beneficiary not found or does not belong to this charity"}), 404

    if item.quantity_available < qty:
        return jsonify({
            "error": "Insufficient quantity",
            "available": item.quantity_available,
            "requested": qty,
        }), 409

    item.quantity_available -= qty
    dist = InventoryDistribution(
        inventory_item_id=item.id,
        beneficiary_id=beneficiary.id,
        quantity=qty,
        notes=data.get("notes"),
    )
    db.session.add(dist)
    db.session.commit()
    return jsonify(_dist_dict(dist)), 201


def _item_dict(i: InventoryItem) -> dict:
    return {
        "id":                 i.id,
        "charity_id":         i.charity_id,
        "item_name":          i.item_name,
        "category":           i.category,
        "unit":               i.unit,
        "quantity_available": i.quantity_available,
        "created_at":         i.created_at.isoformat() if i.created_at else None,
    }


def _dist_dict(d: InventoryDistribution) -> dict:
    return {
        "id":               d.id,
        "inventory_item_id": d.inventory_item_id,
        "beneficiary_id":   d.beneficiary_id,
        "quantity":         d.quantity,
        "distributed_at":   d.distributed_at.isoformat() if d.distributed_at else None,
        "notes":            d.notes,
    }
