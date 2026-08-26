from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from App.model import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'donor')

    if not username or not email or not password:
        return jsonify({'error': 'Username, email and password are required'}), 400

    if role not in ['donor', 'charity', 'admin']:
        return jsonify({'error': 'Invalid role. Must be donor, charity, or admin'}), 400

    if User.query.filter_by(email=email.lower().strip()).first():
        return jsonify({'error': 'User with this email already exists'}), 409

    user = User(
        username=username.strip(),
        email=email.lower().strip(),
        role=role
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Create tokens with claims
    additional_claims = {'role': user.role, 'username': user.username}
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)

    return jsonify({
        'message': 'User registered successfully',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email.lower().strip()).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    additional_claims = {'role': user.role, 'username': user.username}
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)

    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    user_id = get_jwt_identity()
    claims = get_jwt()
    new_claims = {'role': claims.get('role'), 'username': claims.get('username')}
    new_access_token = create_access_token(identity=user_id, additional_claims=new_claims)
    return jsonify({'access_token': new_access_token}), 200
