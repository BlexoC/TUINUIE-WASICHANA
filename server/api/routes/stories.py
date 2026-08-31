"""
server/api/routes/stories.py

GET    /api/stories?charity_id=   — public list of published stories
POST   /api/stories               — charity creates a story
GET    /api/stories/<id>          — public detail
PATCH  /api/stories/<id>          — charity or admin update / publish
DELETE /api/stories/<id>          — charity or admin delete
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import Story
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

stories_bp = Blueprint("stories", __name__)


@stories_bp.get("/")
def list_stories():
    charity_id = request.args.get("charity_id", type=int)
    query = Story.query.filter(Story.published_at.isnot(None))
    if charity_id:
        query = query.filter_by(charity_id=charity_id)
    query = query.order_by(Story.published_at.desc())
    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_story_dict(s) for s in result["items"]]
    return jsonify(result), 200


@stories_bp.post("/")
@jwt_required()
def create_story():
    user = current_user()
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("content"):
        return jsonify({"error": "title and content are required"}), 422

    charity_id = data.get("charity_id") if user.role == "admin" else (user.charity.id if user.charity else None)
    if not charity_id:
        return jsonify({"error": "charity_id required"}), 422

    story = Story(
        charity_id=charity_id,
        beneficiary_id=data.get("beneficiary_id"),
        title=data["title"].strip(),
        content=data["content"],
        image_url=data.get("image_url"),
        published_at=datetime.utcnow() if data.get("publish", False) else None,
    )
    db.session.add(story)
    db.session.commit()
    return jsonify(_story_dict(story)), 201


@stories_bp.get("/<int:story_id>")
def get_story(story_id):
    story = Story.query.get_or_404(story_id)
    return jsonify(_story_dict(story)), 200


@stories_bp.patch("/<int:story_id>")
@jwt_required()
def update_story(story_id):
    story = Story.query.get_or_404(story_id)
    user  = current_user()
    if user.role == "charity" and (not user.charity or user.charity.id != story.charity_id):
        return jsonify({"error": "Forbidden"}), 403
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    for f in ("title", "content", "image_url", "beneficiary_id"):
        if f in data:
            setattr(story, f, data[f])

    if data.get("publish") and not story.published_at:
        story.published_at = datetime.utcnow()
    elif data.get("unpublish"):
        story.published_at = None

    db.session.commit()
    return jsonify(_story_dict(story)), 200


@stories_bp.delete("/<int:story_id>")
@jwt_required()
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    user  = current_user()
    if user.role == "charity" and (not user.charity or user.charity.id != story.charity_id):
        return jsonify({"error": "Forbidden"}), 403
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(story)
    db.session.commit()
    return jsonify({"message": "Story deleted"}), 200


def _story_dict(s: Story) -> dict:
    return {
        "id":             s.id,
        "charity_id":     s.charity_id,
        "beneficiary_id": s.beneficiary_id,
        "title":          s.title,
        "content":        s.content,
        "image_url":      s.image_url,
        "published_at":   s.published_at.isoformat() if s.published_at else None,
        "created_at":     s.created_at.isoformat() if s.created_at else None,
    }
