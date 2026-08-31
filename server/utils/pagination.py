"""
server/utils/pagination.py

Cursor-free offset pagination helper.

Usage:
    page, per_page = get_pagination_params(request)
    query = SomeModel.query.filter(...)
    return paginate(query, page, per_page)
"""

from flask import request, current_app


def get_pagination_params(req=None):
    """
    Extract ?page= and ?per_page= from the current request.
    Clamps per_page to MAX_PAGE_SIZE.
    """
    req = req or request
    try:
        page = max(1, int(req.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(
            max(1, int(req.args.get("per_page", current_app.config["DEFAULT_PAGE_SIZE"]))),
            current_app.config["MAX_PAGE_SIZE"]
        )
    except (TypeError, ValueError):
        per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    return page, per_page


def paginate(query, page: int, per_page: int) -> dict:
    """
    Execute a SQLAlchemy query with pagination and return a standard
    envelope dict ready for jsonify().
    """
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": pagination.items,
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
