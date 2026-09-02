"""
server/__init__.py — Flask application factory
Tuinuie Wasichana — Recurring Charity Donation Platform
"""

import re

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate(directory="server/migrations")
jwt = JWTManager()


def create_app(config_name: str = "development") -> Flask:
    """
    Application factory.

    Usage:
        from server import create_app
        app = create_app("production")
    """
    app = Flask(__name__)

    # ── Load configuration ────────────────────────────────────────────────
    from server.config import config_map
    app.config.from_object(config_map[config_name])

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # In local dev, Vite (and VS Code's port-forwarding) frequently bounces
    # to a different port (5173, 5174, 5175, ...) depending on what else is
    # running. Rather than editing CORS_ORIGINS every time that happens,
    # accept any http(s)://localhost:PORT or 127.0.0.1:PORT origin
    # automatically, on top of whatever's explicitly configured (useful for
    # a real deployed frontend origin in production).
    configured_origins = app.config.get("CORS_ORIGINS", ["http://localhost:3000"])
    localhost_pattern = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")
    allowed_origins = list(configured_origins) + [localhost_pattern]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}},
         supports_credentials=True)

    # ── Register blueprints ───────────────────────────────────────────────
    from server.api.routes.auth import auth_bp
    from server.api.routes.users import users_bp
    from server.api.routes.charities import charities_bp
    from server.api.routes.projects import projects_bp
    from server.api.routes.donations import donations_bp
    from server.api.routes.recurring_plans import plans_bp
    from server.api.routes.beneficiaries import beneficiaries_bp
    from server.api.routes.inventory import inventory_bp
    from server.api.routes.stories import stories_bp
    from server.api.routes.notifications import notifications_bp
    from server.api.routes.admin import admin_bp
    from server.api.routes.payment_methods import payment_methods_bp

    app.register_blueprint(auth_bp,              url_prefix="/api/auth")
    app.register_blueprint(users_bp,             url_prefix="/api/users")
    app.register_blueprint(charities_bp,         url_prefix="/api/charities")
    app.register_blueprint(projects_bp,          url_prefix="/api/projects")
    app.register_blueprint(donations_bp,         url_prefix="/api/donations")
    app.register_blueprint(plans_bp,             url_prefix="/api/recurring-plans")
    app.register_blueprint(beneficiaries_bp,     url_prefix="/api/beneficiaries")
    app.register_blueprint(inventory_bp,         url_prefix="/api/inventory")
    app.register_blueprint(stories_bp,           url_prefix="/api/stories")
    app.register_blueprint(notifications_bp,     url_prefix="/api/notifications")
    app.register_blueprint(admin_bp,             url_prefix="/api/admin")
    app.register_blueprint(payment_methods_bp,   url_prefix="/api/payment-methods")

    # ── JWT token revocation callback (stub — add Redis blocklist here) ───
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return False  # swap with Redis/DB check in production

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has been revoked"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        # 401 (not 422) so the frontend's existing "expired/invalid session"
        # handling — attempt a refresh, then force logout if that fails —
        # actually triggers, instead of the user seeing a dead-end error on
        # every retry until they manually clear localStorage.
        return jsonify({"error": "Invalid token", "detail": str(error)}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"error": "Authorization token is required"}), 401

    # ── Global error handlers ─────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "Tuinuie Wasichana API"})

    return app
