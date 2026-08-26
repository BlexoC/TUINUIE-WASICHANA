from flask import Blueprint, request, jsonify
from App.model import db, Donation, Charity, User, Notification

donation_bp = Blueprint('donation', __name__, url_prefix='/api/donations')

@donation_bp.route('', methods=['GET'])
def get_donations():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    charity_id = request.args.get('charity_id', type=int)
    donor_id = request.args.get('donor_id', type=int)

    query = Donation.query

    if charity_id:
        query = query.filter_by(charity_id=charity_id)
    if donor_id:
        query = query.filter_by(donor_id=donor_id)

    query = query.order_by(Donation.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [d.to_dict() for d in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total_pages': pagination.pages
    }), 200

@donation_bp.route('/one-time', methods=['POST'])
def create_one_time_donation():
    data = request.get_json() or {}
    charity_id = data.get('charity_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'mpesa')

    if not charity_id or not amount:
        return jsonify({'error': 'charity_id and amount are required'}), 400

    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404

    donation = Donation(
        donor_id=data.get('donor_id'),
        donor_name=data.get('donor_name', 'Supporter'),
        donor_email=data.get('donor_email'),
        charity_id=charity_id,
        amount=amount,
        currency=data.get('currency', 'KES'),
        frequency='one-time',
        payment_method=payment_method,
        payment_status='completed',
        mpesa_phone=data.get('mpesa_phone'),
        mpesa_receipt=data.get('mpesa_receipt', f"TW{int(amount)}"),
        stripe_payment_id=data.get('stripe_payment_id'),
        is_anonymous=data.get('is_anonymous', False),
        message=data.get('message')
    )

    db.session.add(donation)
    charity.raised_amount = float(charity.raised_amount or 0) + float(amount)
    db.session.commit()

    return jsonify({
        'message': 'Donation recorded successfully',
        'donation': donation.to_dict()
    }), 201

@donation_bp.route('/recurring', methods=['POST'])
def create_recurring_donation():
    data = request.get_json() or {}
    charity_id = data.get('charity_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'stripe')

    if not charity_id or not amount:
        return jsonify({'error': 'charity_id and amount are required'}), 400

    charity = Charity.query.get(charity_id)
    if not charity:
        return jsonify({'error': 'Charity not found'}), 404

    donation = Donation(
        donor_id=data.get('donor_id'),
        donor_name=data.get('donor_name', 'Monthly Benefactor'),
        donor_email=data.get('donor_email'),
        charity_id=charity_id,
        amount=amount,
        currency=data.get('currency', 'KES'),
        frequency='monthly',
        payment_method=payment_method,
        payment_status='completed',
        stripe_payment_id=data.get('stripe_payment_id', 'sub_mock_active'),
        is_anonymous=data.get('is_anonymous', False),
        message=data.get('message', 'Monthly contribution for dignity supplies.')
    )

    db.session.add(donation)
    charity.raised_amount = float(charity.raised_amount or 0) + float(amount)
    db.session.commit()

    return jsonify({
        'message': 'Monthly recurring donation created successfully',
        'donation': donation.to_dict()
    }), 201

@donation_bp.route('/summary', methods=['GET'])
def get_donations_summary():
    total_amount = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_donations = Donation.query.count()
    unique_donors = db.session.query(db.func.count(db.func.distinct(Donation.donor_email))).scalar() or 0

    return jsonify({
        'total_amount_raised': float(total_amount),
        'total_donations_count': total_donations,
        'unique_donors_count': unique_donors,
        'currency': 'KES'
    }), 200
