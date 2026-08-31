"""
server/api/routes/projects.py

GET    /api/projects                        — public list (filterable by charity)
POST   /api/projects                        — charity creates a project
GET    /api/projects/<id>                   — public detail + funding progress
PATCH  /api/projects/<id>                   — charity owner or admin update
DELETE /api/projects/<id>                   — archive (soft-delete)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import CharityProject
from server.api.middleware.auth import current_user
from server.utils.pagination import get_pagination_params, paginate

projects_bp = Blueprint("projects", __name__)


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------
@projects_bp.get("/")
def list_projects():
    """
    Public list.  Filter by ?charity_id=&status=active|completed|archived
    """
    charity_id = request.args.get("charity_id", type=int)
    status     = request.args.get("status", "active")

    query = CharityProject.query
    if charity_id:
        query = query.filter_by(charity_id=charity_id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(CharityProject.is_urgent.desc(), CharityProject.created_at.desc())

    page, per_page = get_pagination_params()
    result = paginate(query, page, per_page)
    result["items"] = [_project_dict(p) for p in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------
@projects_bp.post("/")
@jwt_required()
def create_project():
    user = current_user()
    if user.role not in ("charity", "admin"):
        return jsonify({"error": "Only charity accounts may create projects"}), 403

    data = request.get_json(silent=True) or {}

    # Determine charity_id
    if user.role == "admin":
        charity_id = data.get("charity_id")
        if not charity_id:
            return jsonify({"error": "charity_id is required for admin-created projects"}), 422
    else:
        if not user.charity:
            return jsonify({"error": "Charity profile not found"}), 403
        charity_id = user.charity.id

    required = ("title", "goal_amount")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    try:
        goal = float(data["goal_amount"])
        if goal <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "goal_amount must be a positive number"}), 422

    project = CharityProject(
        charity_id=charity_id,
        title=data["title"].strip(),
        description=data.get("description"),
        category=data.get("category"),
        image_url=data.get("image_url"),
        goal_amount=goal,
        is_urgent=bool(data.get("is_urgent", False)),
        status="active",
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(_project_dict(project)), 201


# ---------------------------------------------------------------------------
# GET /api/projects/<id>
# ---------------------------------------------------------------------------
@projects_bp.get("/<int:project_id>")
def get_project(project_id):
    project = CharityProject.query.get_or_404(project_id)
    return jsonify(_project_dict(project)), 200


# ---------------------------------------------------------------------------
# PATCH /api/projects/<id>
# ---------------------------------------------------------------------------
@projects_bp.patch("/<int:project_id>")
@jwt_required()
def update_project(project_id):
    project = CharityProject.query.get_or_404(project_id)
    user = current_user()

    if user.role == "charity":
        if not user.charity or user.charity.id != project.charity_id:
            return jsonify({"error": "You do not own this project"}), 403
    elif user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    for field in ("title", "description", "category", "image_url", "is_urgent"):
        if field in data:
            setattr(project, field, data[field])

    if "goal_amount" in data:
        try:
            goal = float(data["goal_amount"])
            if goal <= 0:
                raise ValueError
            project.goal_amount = goal
        except (TypeError, ValueError):
            return jsonify({"error": "goal_amount must be a positive number"}), 422

    if "status" in data:
        if data["status"] not in ("active", "completed", "archived"):
            return jsonify({"error": "Invalid status"}), 422
        project.status = data["status"]

    db.session.commit()
    return jsonify(_project_dict(project)), 200


# ---------------------------------------------------------------------------
# DELETE /api/projects/<id>  — soft archive
# ---------------------------------------------------------------------------
@projects_bp.delete("/<int:project_id>")
@jwt_required()
def archive_project(project_id):
    project = CharityProject.query.get_or_404(project_id)
    user = current_user()

    if user.role == "charity":
        if not user.charity or user.charity.id != project.charity_id:
            return jsonify({"error": "You do not own this project"}), 403
    elif user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    project.status = "archived"
    db.session.commit()
    return jsonify({"message": "Project archived", "project_id": project_id}), 200


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------
def _project_dict(p: CharityProject) -> dict:
    return {
        "id":             p.id,
        "charity_id":     p.charity_id,
        "title":          p.title,
        "description":    p.description,
        "category":       p.category,
        "image_url":      p.image_url,
        "goal_amount":    str(p.goal_amount),
        "amount_raised":  str(p.amount_raised),
        "percent_funded": p.percent_funded,
        "is_urgent":      p.is_urgent,
        "status":         p.status,
        "created_at":     p.created_at.isoformat() if p.created_at else None,
        "updated_at":     p.updated_at.isoformat() if p.updated_at else None,
    }
