from flask import Blueprint, request, jsonify
from datetime import datetime
from App.model import db, Beneficiary, Charity

beneficiary_bp = Blueprint('beneficiary', __name__, url_prefix='/api')

@beneficiary_bp.route('/charities/<int:charity_id>/beneficiaries', methods=['GET'])
def get_charity_beneficiaries(charity_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    search = request.args.get('search')

    query = Beneficiary.query.filter_by(charity_id=charity_id)

    if status and status != 'all':
        query = query.filter_by(status=status)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            db.or_(
                Beneficiary.full_name.ilike(search_term),
                Beneficiary.school_name.ilike(search_term)
            )
        )

    query = query.order_by(Beneficiary.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [b.to_dict() for b in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages
    }), 200

@beneficiary_bp.route('/charities/<int:charity_id>/beneficiaries', methods=['POST'])
def add_beneficiary(charity_id):
    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404

    data = request.get_json() or {}
    full_name = data.get('full_name')
    school_name = data.get('school_name')
    age = data.get('age')

    if not full_name or not school_name or not age:
        return jsonify({'error': 'Full name, school name and age are required'}), 400

    beneficiary = Beneficiary(
        charity_id=charity_id,
        full_name=full_name.strip(),
        age=int(age),
        school_name=school_name.strip(),
        grade_level=data.get('grade_level', 'Grade 8'),
        kits_received=data.get('kits_received', 1),
        attendance_rate=data.get('attendance_rate', 95),
        story=data.get('story', 'Enrolled in menstrual hygiene support initiative.'),
        status=data.get('status', 'active'),
        last_kit_date=datetime.utcnow().date()
    )

    db.session.add(beneficiary)
    db.session.commit()

    return jsonify({
        'message': 'Beneficiary registered successfully',
        'beneficiary': beneficiary.to_dict()
    }), 201

@beneficiary_bp.route('/beneficiaries/<int:beneficiary_id>', methods=['PUT'])
def update_beneficiary(beneficiary_id):
    beneficiary = Beneficiary.query.get(beneficiary_id)
    if not beneficiary:
        return jsonify({'error': 'Beneficiary not found'}), 404

    data = request.get_json() or {}
    if 'full_name' in data:
        beneficiary.full_name = data['full_name']
    if 'school_name' in data:
        beneficiary.school_name = data['school_name']
    if 'grade_level' in data:
        beneficiary.grade_level = data['grade_level']
    if 'kits_received' in data:
        beneficiary.kits_received = data['kits_received']
    if 'attendance_rate' in data:
        beneficiary.attendance_rate = data['attendance_rate']
    if 'story' in data:
        beneficiary.story = data['story']
    if 'status' in data:
        beneficiary.status = data['status']

    db.session.commit()
    return jsonify({
        'message': 'Beneficiary updated successfully',
        'beneficiary': beneficiary.to_dict()
    }), 200

@beneficiary_bp.route('/beneficiaries/<int:beneficiary_id>/distribute-kit', methods=['POST'])
def log_kit_distribution(beneficiary_id):
    beneficiary = Beneficiary.query.get(beneficiary_id)
    if not beneficiary:
        return jsonify({'error': 'Beneficiary not found'}), 404

    beneficiary.kits_received += 1
    beneficiary.last_kit_date = datetime.utcnow().date()
    db.session.commit()

    return jsonify({
        'message': 'Kit distribution recorded',
        'beneficiary': beneficiary.to_dict()
    }), 200

@beneficiary_bp.route('/beneficiaries/<int:beneficiary_id>', methods=['DELETE'])
def delete_beneficiary(beneficiary_id):
    beneficiary = Beneficiary.query.get(beneficiary_id)
    if not beneficiary:
        return jsonify({'error': 'Beneficiary not found'}), 404

    db.session.delete(beneficiary)
    db.session.commit()
    return jsonify({'message': 'Beneficiary record removed'}), 200
