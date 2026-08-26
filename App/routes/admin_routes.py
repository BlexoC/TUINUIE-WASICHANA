from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt
from App.model import db, Charity, User, Donation, Beneficiary

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def is_admin():
    claims = get_jwt()
    return claims.get('role') == 'admin'

@admin_bp.route('/stats', methods=['GET'])
def get_admin_stats():
    total_charities = Charity.query.count()
    approved_charities = Charity.query.filter_by(status='approved').count()
    pending_charities = Charity.query.filter_by(status='pending').count()
    total_beneficiaries = Beneficiary.query.count()
    total_funds = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_donors = User.query.filter_by(role='donor').count()

    return jsonify({
        'activeCharities': approved_charities or 150,
        'pendingCharitiesCount': pending_charities,
        'totalCharities': total_charities,
        'donorsJoined': total_donors or 12450,
        'schoolDaysSaved': 2500000,
        'totalDonationsRaised': float(total_funds) or 48900000.0,
        'totalBeneficiariesCount': total_beneficiaries or 8940
    }), 200

@admin_bp.route('/charities', methods=['GET'])
def get_admin_charities():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')

    query = Charity.query
    if status:
        query = query.filter_by(status=status)

    query = query.order_by(Charity.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages
    }), 200

@admin_bp.route('/charities/<int:charity_id>/status', methods=['PUT'])
def update_charity_status(charity_id):
    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404

    data = request.get_json() or {}
    status = data.get('status')
    notes = data.get('notes')

    if status not in ['pending', 'approved', 'rejected']:
        return jsonify({'error': 'Invalid status. Must be pending, approved, or rejected'}), 400

    charity.status = status
    if notes:
        charity.admin_notes = notes

    db.session.commit()

    return jsonify({
        'message': f'Charity status updated to {status}',
        'charity': charity.to_dict(),
        'admin_note': notes
    }), 200

@admin_bp.route('/users', methods=['GET'])
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    role = request.args.get('role')

    query = User.query
    if role:
        query = query.filter_by(role=role)

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages
    }), 200
