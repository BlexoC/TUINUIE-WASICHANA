"""
server/api/routes/mpesa.py  (patched)

POST  /api/mpesa/stkpush   — donor triggers STK push (JWT required)
POST  /api/mpesa/query     — donor polls for payment status (JWT required)
POST  /api/mpesa/callback  — Safaricom posts the payment result here (no auth)

Change from the previous version: donor_id/charity_id/project_id/amount are
now recorded in MpesaCheckoutRequest at the moment we initiate the push,
keyed by checkout_request_id. The callback looks up that record instead of
trying to reconstruct AccountReference or match by phone number — both of
which are unreliable (Daraja doesn't echo AccountReference back, and most
one-time donors won't have a saved PaymentMethod to match against).
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from server import db
from server.models import Charity, Donation, MpesaCheckoutRequest, Notification
from server.api.middleware.auth import current_user
from server.services import mpesa as mpesa_service

logger = logging.getLogger(__name__)

mpesa_bp = Blueprint("mpesa", __name__)


# ---------------------------------------------------------------------------
# POST /api/mpesa/stkpush
# ---------------------------------------------------------------------------
@mpesa_bp.post("/stkpush")
@jwt_required()
def stkpush():
    """
    Initiate an M-Pesa STK push.

    Body (JSON):
        phone       str   required  — donor's Safaricom number
        amount      int   required  — amount in KES (must be positive integer)
        charity_id  int   required  — charity to donate to
        project_id  int   optional  — specific project within the charity
    """
    user = current_user()
    if user.role != "donor" or not user.donor:
        return jsonify({"error": "Donor account required"}), 403

    data = request.get_json(silent=True) or {}
    required = ("phone", "amount", "charity_id")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    charity = Charity.query.get(data["charity_id"])
    if not charity or charity.status != "active":
        return jsonify({"error": "Charity not found or inactive"}), 404

    try:
        amount = int(data["amount"])
        if amount < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive integer (KES)"}), 422

    phone = str(data["phone"]).strip()
    if not phone:
        return jsonify({"error": "phone is required"}), 422

    project_id = data.get("project_id")

    account_ref = f"TW{data['charity_id']}"
    description = "TuinueDonation"

    try:
        daraja_resp = mpesa_service.stk_push(
            phone=phone,
            amount=amount,
            account_reference=account_ref,
            description=description,
        )
    except RuntimeError as e:
        logger.error("M-Pesa config error: %s", e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error("Daraja STK push failed: %s", e)
        return jsonify({"error": "M-Pesa gateway error. Please try again."}), 502

    if daraja_resp.get("ResponseCode") != "0":
        return jsonify({
            "error": daraja_resp.get("ResponseDescription", "STK push failed"),
            "daraja": daraja_resp,
        }), 400

    checkout_request_id = daraja_resp["CheckoutRequestID"]

    # Record the request now, while we still reliably know who it's for.
    # This is the record the callback will look up — not AccountReference.
    checkout_record = MpesaCheckoutRequest(
        checkout_request_id=checkout_request_id,
        merchant_request_id=daraja_resp.get("MerchantRequestID"),
        donor_id=user.donor.id,
        charity_id=data["charity_id"],
        project_id=project_id,
        phone_number=phone,
        amount=amount,
        status="pending",
    )
    db.session.add(checkout_record)
    db.session.commit()

    return jsonify({
        "message": daraja_resp.get("CustomerMessage", "Check your phone"),
        "checkout_request_id": checkout_request_id,
        "merchant_request_id": daraja_resp.get("MerchantRequestID"),
    }), 200


# ---------------------------------------------------------------------------
# POST /api/mpesa/query
# ---------------------------------------------------------------------------
@mpesa_bp.post("/query")
@jwt_required()
def query_stk():
    """
    Poll Daraja for the status of a pending STK push. Also checks our own
    record first — if the callback already resolved it, no need to hit
    Daraja again (their sandbox query endpoint is known to be flaky).
    """
    data = request.get_json(silent=True) or {}
    checkout_request_id = (data.get("checkout_request_id") or "").strip()
    if not checkout_request_id:
        return jsonify({"error": "checkout_request_id is required"}), 422

    record = MpesaCheckoutRequest.query.filter_by(
        checkout_request_id=checkout_request_id
    ).first()

    if record and record.status != "pending":
        return jsonify({
            "result_code": record.result_code,
            "result_desc": record.result_desc,
            "status": record.status,
        }), 200

    try:
        result = mpesa_service.stk_query(checkout_request_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error("Daraja STK query failed: %s", e)
        # Don't fail hard — the callback may still resolve this even if the
        # live query endpoint is having issues (known sandbox flakiness).
        return jsonify({"status": "pending", "note": "query endpoint unavailable, still waiting on callback"}), 200

    return jsonify({
        "result_code": result.get("ResultCode"),
        "result_desc": result.get("ResultDesc"),
        "raw": result,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/mpesa/callback  (called by Safaricom — no JWT)
# ---------------------------------------------------------------------------
@mpesa_bp.post("/callback")
def mpesa_callback():
    """
    Safaricom posts the final STK push result to this URL. We look the
    transaction up by CheckoutRequestID — the only value Daraja reliably
    echoes back — rather than trying to parse AccountReference (not sent)
    or match by phone number (unreliable for one-time donors).
    """
    try:
        body = request.get_json(force=True, silent=True) or {}
        parsed = mpesa_service.parse_stk_callback(body)

        checkout_request_id = parsed["checkout_request_id"]
        result_code = parsed["result_code"]

        logger.info(
            "M-Pesa callback: checkout_id=%s result_code=%s",
            checkout_request_id, result_code,
        )

        record = MpesaCheckoutRequest.query.filter_by(
            checkout_request_id=checkout_request_id
        ).first()

        if not record:
            logger.error(
                "M-Pesa callback for unknown checkout_request_id=%s — "
                "no matching MpesaCheckoutRequest. Cannot record donation "
                "automatically; needs manual reconciliation. Raw payload: %s",
                checkout_request_id, body,
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        # Idempotency: Daraja may retry the callback. If we've already
        # resolved this record, don't process it again.
        if record.status != "pending":
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        if not parsed["success"]:
            record.status = "failed"
            record.result_code = result_code
            record.result_desc = parsed["result_desc"]
            db.session.commit()
            logger.warning(
                "M-Pesa payment failed: checkout_id=%s result_code=%s desc=%s",
                checkout_request_id, result_code, parsed["result_desc"],
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        receipt_number = parsed["mpesa_receipt_number"]
        amount = parsed["amount"] or record.amount

        # Extra idempotency guard: skip if this receipt was already recorded
        # under a different checkout request somehow.
        existing = Donation.query.filter_by(
            payment_provider="mpesa",
            provider_transaction_id=receipt_number,
        ).first()
        if existing:
            record.status = "completed"
            record.mpesa_receipt_number = receipt_number
            record.result_code = result_code
            record.result_desc = parsed["result_desc"]
            record.donation_id = existing.id
            db.session.commit()
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        donation = Donation(
            donor_id=record.donor_id,
            charity_id=record.charity_id,
            donation_type="one_time",
            amount=amount,
            currency="KES",
            is_anonymous=False,
            payment_provider="mpesa",
            provider_transaction_id=receipt_number,
            payment_status="completed",
        )
        db.session.add(donation)
        db.session.flush()

        record.status = "completed"
        record.mpesa_receipt_number = receipt_number
        record.result_code = result_code
        record.result_desc = parsed["result_desc"]
        record.donation_id = donation.id

        charity = record.charity
        db.session.add(Notification(
            user_id=record.donor.user_id,
            type="donation_successful",
            title="M-Pesa donation confirmed",
            message=(
                f"Your M-Pesa payment of KES {amount:,.0f} "
                f"to {charity.name} was received. Receipt: {receipt_number}"
            ),
            related_entity_type="donation",
            related_entity_id=donation.id,
        ))
        db.session.commit()

        logger.info(
            "Recorded M-Pesa donation: receipt=%s amount=%s charity=%s donor=%s",
            receipt_number, amount, record.charity_id, record.donor_id,
        )

    except Exception:
        db.session.rollback()
        logger.exception("Unhandled error in M-Pesa callback")

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200