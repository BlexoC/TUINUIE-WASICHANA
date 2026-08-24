from flask import Flask, jsonify, request
import flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost:5432/tuinue_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints 
    from app.routes.charities import charities_bp
    app.register_blueprint(charities_bp, url_prefix='/api/charities')


    return app


