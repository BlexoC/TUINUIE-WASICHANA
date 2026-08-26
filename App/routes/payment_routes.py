from flask import Blueprint, request, jsonify
import time
from App.model import db, Donation, Charity

payment_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

@payment_bp.route('/mpesa/stk-push', methods=['POST'])
def mpesa_stk_push():
    data = request.get_json() or {}
    phone_number = data.get('phone_number')
    amount = data.get('amount')
    charity_id = data.get('charity_id')

    if not phone_number or not amount:
        return jsonify({'error': 'phone_number and amount required'}), 400

    checkout_id = f"ws_CO_{int(time.time())}_MPESA"
    receipt = f"TW{int(time.time()) % 100000}"

    if charity_id:
        charity = Charity.query.get(charity_id)
        if charity:
            charity.raised_amount = float(charity.raised_amount or 0) + float(amount)
            donation = Donation(
                donor_name=data.get('donor_name', 'M-Pesa Donor'),
                charity_id=charity_id,
                amount=amount,
                currency='KES',
                frequency=data.get('frequency', 'one-time'),
                payment_method='mpesa',
                payment_status='completed',
                mpesa_phone=phone_number,
                mpesa_receipt=receipt
            )
            db.session.add(donation)
            db.session.commit()

    return jsonify({
        'ResponseCode': '0',
        'ResponseDescription': 'Success. Request accepted for processing',
        'CheckoutRequestID': checkout_id,
        'ReceiptNumber': receipt,
        'CustomerMessage': 'STK Push sent to mobile device. Please complete PIN confirmation.'
    }), 200

@payment_bp.route('/stripe/create-intent', methods=['POST'])
def stripe_create_intent():
    data = request.get_json() or {}
    amount = data.get('amount')
    currency = data.get('currency', 'usd')
    charity_id = data.get('charity_id')

    if not amount:
        return jsonify({'error': 'Amount required'}), 400

    intent_id = f"pi_mock_{int(time.time())}"
    client_secret = f"{intent_id}_secret_xyz"

    if charity_id:
        charity = Charity.query.get(charity_id)
        if charity:
            kes_amount = float(amount) * 130 if currency.lower() == 'usd' else float(amount)
            charity.raised_amount = float(charity.raised_amount or 0) + kes_amount
            donation = Donation(
                donor_name=data.get('donor_name', 'Stripe Donor'),
                charity_id=charity_id,
                amount=amount,
                currency=currency.upper(),
                frequency=data.get('frequency', 'one-time'),
                payment_method='stripe',
                payment_status='completed',
                stripe_payment_id=intent_id
            )
            db.session.add(donation)
            db.session.commit()

    return jsonify({
        'clientSecret': client_secret,
        'status': 'succeeded'
    }), 200
