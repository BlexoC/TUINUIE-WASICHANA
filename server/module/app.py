from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)

# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "super-secret-key-change-this-in-prod"  # Add JWT Secret

# Extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# Import models after db initialization to avoid circular imports
from model import Donor

# ----------------------------------------
# BE-002: Donor Login Endpoint
# ----------------------------------------
@app.route('/api/donors/login', methods=['POST'])
def donor_login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"message": "Email and password are required"}), 400

    email = data.get('email').strip().lower()
    password = data.get('password')

    # 1. Fetch donor from DB
    donor = Donor.query.filter_by(email=email).first()

    # 2. Validate user existence and password match
    if not donor or not donor.check_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    # 3. Create JWT token
    access_token = create_access_token(identity={"id": donor.id, "email": donor.email, "role": "donor"})

    return jsonify({
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "donor": {
            "id": donor.id,
            "email": donor.email
        }
    }), 200

# ----------------------------------------
# Protected Route Example
# ----------------------------------------
@app.route('/api/donors/profile', methods=['GET'])
@jwt_required()
def get_donor_profile():
    current_user = get_jwt_identity()
    return jsonify({
        "success": True,
        "donor": current_user
    }), 200

if __name__ == "__main__":
    app.run(debug=True)