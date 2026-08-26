from flask import Blueprint, request, jsonify
from App.model import db, Charity, User

charity_bp = Blueprint('charity', __name__, url_prefix='/api/charities')

@charity_bp.route('', methods=['GET'])
def get_charities():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 6, type=int)
    category = request.args.get('category')
    search = request.args.get('search')
    status = request.args.get('status', 'approved')

    query = Charity.query

    if status and status != 'all':
        query = query.filter_by(status=status)

    if category and category != 'All':
        query = query.filter(Charity.category.ilike(f"%{category}%"))

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            db.or_(
                Charity.name.ilike(search_term),
                Charity.mission_statement.ilike(search_term),
                Charity.address.ilike(search_term)
            )
        )

    query = query.order_by(Charity.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages
    }), 200

@charity_bp.route('/<int:charity_id>', methods=['GET'])
def get_charity(charity_id):
    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404
    return jsonify(charity.to_dict()), 200

@charity_bp.route('', methods=['POST'])
def register_charity():
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    mission_statement = data.get('mission_statement')

    if not name or not email or not mission_statement:
        return jsonify({'error': 'Organization name, email and mission statement are required'}), 400

    user_id = data.get('user_id')

    charity = Charity(
        user_id=user_id,
        name=name.strip(),
        year_established=data.get('year_established', '2024'),
        org_type=data.get('org_type', 'NGO'),
        mission_statement=mission_statement.strip(),
        address=data.get('address', 'Nairobi, Kenya'),
        email=email.strip(),
        phone=data.get('phone', ''),
        website=data.get('website', ''),
        contact_person=data.get('contact_person', ''),
        status='pending', # Approval workflow
        category=data.get('category', 'Sanitary Distribution'),
        target_amount=data.get('target_amount', 500000.00),
        raised_amount=0.00,
        currency=data.get('currency', 'KES'),
        image_url=data.get('image_url', '/src/assets/images/hero_schoolgirls_1787607019295.jpg'),
        ngo_cert_url=data.get('ngo_cert_url', 'ngo_cert.pdf'),
        audit_doc_url=data.get('audit_doc_url', 'financial_audit.pdf'),
        director_id_url=data.get('director_id_url', 'director_id.pdf'),
        what_they_do=data.get('what_they_do', mission_statement),
        how_it_started=data.get('how_it_started', 'Grassroots organization founded to combat period poverty.'),
        impact_summary=data.get('impact_summary', 'Application submitted for platform accreditation.')
    )

    db.session.add(charity)
    db.session.commit()

    return jsonify({
        'message': 'Charity application submitted successfully and queued for admin review.',
        'charity': charity.to_dict()
    }), 201

@charity_bp.route('/<int:charity_id>/stats', methods=['GET'])
def get_charity_stats(charity_id):
    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404

    beneficiaries_count = len(charity.beneficiaries)
    donations_count = len(charity.donations)
    return jsonify({
        'charity_id': charity.id,
        'charity_name': charity.name,
        'target_amount': float(charity.target_amount),
        'raised_amount': float(charity.raised_amount),
        'progress_percent': round((float(charity.raised_amount) / float(charity.target_amount) * 100), 1) if charity.target_amount > 0 else 0,
        'beneficiaries_count': beneficiaries_count,
        'donations_count': donations_count
    }), 200
