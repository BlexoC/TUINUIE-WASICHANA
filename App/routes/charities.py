from flask import Blueprint, request, jsonify
from app import db
from app.models import Charity, User

charities_bp = Blueprint('charities', __name__)

# Charity Application / Charity Registration
@charities_bp.route('/apply', methods=['POST'])
def apply_charity():
    data = request.get_json() or {}

    required_fields = ['email', 'password', 'name', 'registration_number']
    if not all(k in data for k in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "User with this email already exists"}), 400

    # Create associated user account
    user = User(email=data['email'], password_hash=data['password'], role='charity_admin')
    db.session.add(user)
    db.session.flush()

    # Create charity application record (Status defaults to 'pending')
    charity = Charity(
        user_id=user.id,
        name=data['name'],
        description=data.get('description', ''),
        registration_number=data['registration_number']
    )
    db.session.add(charity)
    db.session.commit()

    return jsonify({
        "message": "Application submitted successfully. Awaiting admin approval.",
        "charity": charity.to_dict()
    }), 201


# Charity Listings API (with mandatory Pagination)
@charities_bp.route('', methods=['GET'])
def get_charities():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Query only approved charities for general listings
    pagination = Charity.query.filter_by(status='approved').paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "data": [charity.to_dict() for charity in pagination.items],
        "meta": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_items": pagination.total,
            "total_pages": pagination.pages
        }
    }), 200


# Charity Details API
@charities_bp.route('/<int:charity_id>', methods=['GET'])
def get_charity_details(charity_id):
    charity = Charity.query.get_or_404(charity_id)
    return jsonify(charity.to_dict()), 200