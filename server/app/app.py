"""Flask application and database extension instances."""

import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate(compare_type=True)


def create_app(test_config: dict | None = None) -> Flask:
    """Create the application with a configurable SQLAlchemy connection."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///app.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import after db is initialized so Alembic can discover every model.
    from app import models  # noqa: F401
    from app.routes.charity import charity_bp

    app.register_blueprint(charity_bp)

    return app


app = create_app()
