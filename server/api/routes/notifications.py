"""
server/api/routes/notifications.py

GET    /api/notifications                  — current user's notifications
PATCH  /api/notifications/<id>/read        — mark one as read
POST   /api/notifications/read-all         — mark all as read
DELETE /api/notifications/<id>             — delete one
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import Notification
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("/")
@jwt_required()
def list_notifications():
    user     = current_user()
    unread   = request.args.get("unread")
    query    = Notification.query.filter_by(user_id=user.id)
    if unread == "true":
        query = query.filter_by(is_read=False)
    query = query.order_by(Notification.created_at.desc())
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_n_dict(n) for n in result["items"]]
    result["unread_count"] = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify(result), 200


@notifications_bp.patch("/<int:notif_id>/read")
@jwt_required()
def mark_read(notif_id):
    user   = current_user()
    notif  = Notification.query.get_or_404(notif_id)
    if notif.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"}), 200


@notifications_bp.post("/read-all")
@jwt_required()
def mark_all_read():
    user = current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "All notifications marked as read"}), 200


@notifications_bp.delete("/<int:notif_id>")
@jwt_required()
def delete_notification(notif_id):
    user  = current_user()
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(notif)
    db.session.commit()
    return jsonify({"message": "Notification deleted"}), 200


def _n_dict(n: Notification) -> dict:
    return {
        "id":                  n.id,
        "type":                n.type,
        "title":               n.title,
        "message":             n.message,
        "is_read":             n.is_read,
        "related_entity_type": n.related_entity_type,
        "related_entity_id":   n.related_entity_id,
        "created_at":          n.created_at.isoformat() if n.created_at else None,
    }
