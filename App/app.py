from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from App.config import Config
from App.model import db
from App.routes.auth_routes import auth_bp
from App.routes.charity_routes import charity_bp
from App.routes.donation_routes import donation_bp
from App.routes.beneficiary_routes import beneficiary_bp
from App.routes.admin_routes import admin_bp
from App.routes.payment_routes import payment_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app)
    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(charity_bp)
    app.register_blueprint(donation_bp)
    app.register_blueprint(beneficiary_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payment_bp)

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'app': 'Tuinue Wasichana API'})

    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
