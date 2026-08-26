from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# create extensions without binding to an app so create_app can initialize
db = SQLAlchemy()
migrate = Migrate()


def create_app(config: dict | None = None):
	"""Application factory for tests and production.

	Accepts an optional mapping of config values.
	"""
	app = Flask(__name__)

	# sensible defaults
	app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///app.db")
	app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

	if config:
		app.config.update(config)

	# initialize extensions
	db.init_app(app)
	migrate.init_app(app, db)

	# import and register all blueprints defined in the routes package
	try:
		from . import routes as _routes

		for name in getattr(_routes, "__all__", []):
			bp = getattr(_routes, name, None)
			if bp is not None:
				app.register_blueprint(bp)
	except Exception:
		# deferred import errors should not break app import in tests/setup
		pass

	return app


# convenience top-level app for simple imports
app = create_app()