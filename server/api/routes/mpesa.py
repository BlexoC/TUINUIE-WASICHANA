"""
server/api/routes/mpesa.py

POST  /api/mpesa/stkpush   — donor triggers STK push (JWT required)
POST  /api/mpesa/query     — donor polls for payment status (JWT required)
POST  /api/mpesa/callback  — Safaricom posts the payment result here (no auth)

Flow:
  1. Frontend calls POST /api/mpesa/stkpush → backend calls Daraja → returns
     checkout_request_id to frontend.
  2. Frontend polls POST /api/mpesa/query every 3 s until ResultCode = "0"
     (success) or a known failure code.
  3. Safaricom also calls POST /api/mpesa/callback asynchronously with the
     final result — this is the authoritative record; the backend records
     the donation here and sends the donor a notification.
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from server import db
from server.models import User, Donor, Charity, Donation, Notification
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

    # Validate charity
    charity = Charity.query.get(data["charity_id"])
    if not charity or charity.status != "active":
        return jsonify({"error": "Charity not found or inactive"}), 404

    # Validate amount
    try:
        amount = int(data["amount"])
        if amount < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive integer (KES)"}), 422

    phone = str(data["phone"]).strip()
    if not phone:
        return jsonify({"error": "phone is required"}), 422

    account_ref  = f"TW{data['charity_id']}"          # shown on donor's phone
    description  = "TuinueDonation"

    try:
        daraja_resp = mpesa_service.stk_push(
            phone=phone,
            amount=amount,
            account_reference=account_ref,
            description=description,
        )
    except RuntimeError as e:
        # Missing credentials — helpful error for the developer
        logger.error("M-Pesa config error: %s", e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error("Daraja STK push failed: %s", e)
        return jsonify({"error": "M-Pesa gateway error. Please try again."}), 502

    # ResponseCode "0" means the request was accepted (not yet paid)
    if daraja_resp.get("ResponseCode") != "0":
        return jsonify({
            "error": daraja_resp.get("ResponseDescription", "STK push failed"),
            "daraja": daraja_resp,
        }), 400

    return jsonify({
        "message":              daraja_resp.get("CustomerMessage", "Check your phone"),
        "checkout_request_id":  daraja_resp["CheckoutRequestID"],
        "merchant_request_id":  daraja_resp["MerchantRequestID"],
    }), 200


# ---------------------------------------------------------------------------
# POST /api/mpesa/query
# ---------------------------------------------------------------------------
@mpesa_bp.post("/query")
@jwt_required()
def query_stk():
    """
    Poll Daraja for the status of a pending STK push.

    Body (JSON):
        checkout_request_id  str  required

    Returns:
        { "result_code": "0", "result_desc": "..." }

    result_code "0"    → payment confirmed
    result_code "1032" → user cancelled
    result_code "1037" → timed out
    other              → failure
    """
    data = request.get_json(silent=True) or {}
    checkout_request_id = data.get("checkout_request_id", "").strip()
    if not checkout_request_id:
        return jsonify({"error": "checkout_request_id is required"}), 422

    try:
        result = mpesa_service.stk_query(checkout_request_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error("Daraja STK query failed: %s", e)
        return jsonify({"error": "Could not query payment status"}), 502

    return jsonify({
        "result_code": result.get("ResultCode"),
        "result_desc": result.get("ResultDesc"),
        "raw":         result,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/mpesa/callback  (called by Safaricom — no JWT)
# ---------------------------------------------------------------------------
@mpesa_bp.post("/callback")
def mpesa_callback():
    """
    Safaricom posts the final STK push result to this URL.

    This is the authoritative record of a completed payment.  We:
      1. Parse the result.
      2. On success, find or create the Donation row and send a notification.
      3. Always return 200 — Safaricom retries on anything else.

    The callback body shape (from Daraja docs):
    {
      "Body": {
        "stkCallback": {
          "MerchantRequestID": "...",
          "CheckoutRequestID": "...",
          "ResultCode": 0,
          "ResultDesc": "The service request is processed successfully.",
          "CallbackMetadata": {
            "Item": [
              {"Name": "Amount",              "Value": 500},
              {"Name": "MpesaReceiptNumber",  "Value": "NLJ7RT61SV"},
              {"Name": "TransactionDate",     "Value": 20191219102115},
              {"Name": "PhoneNumber",         "Value": 254708374149}
            ]
          }
        }
      }
    }
    On failure ResultCode != 0 and CallbackMetadata is absent.
    """
    try:
        body       = request.get_json(force=True, silent=True) or {}
        callback   = body.get("Body", {}).get("stkCallback", {})
        result_code = int(callback.get("ResultCode", -1))

        checkout_request_id = callback.get("CheckoutRequestID", "")
        merchant_request_id = callback.get("MerchantRequestID", "")

        logger.info(
            "M-Pesa callback: checkout_id=%s result_code=%s",
            checkout_request_id, result_code,
        )

        if result_code != 0:
            # Payment failed / cancelled — nothing to record
            logger.warning(
                "M-Pesa payment failed: %s — %s",
                result_code, callback.get("ResultDesc"),
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        # Extract metadata items
        items = {
            item["Name"]: item.get("Value")
            for item in callback.get("CallbackMetadata", {}).get("Item", [])
            if "Value" in item
        }

        receipt_number = str(items.get("MpesaReceiptNumber", ""))
        amount         = float(items.get("Amount", 0))
        phone          = str(items.get("PhoneNumber", ""))

        if not receipt_number or amount <= 0:
            logger.error("M-Pesa callback missing receipt/amount: %s", items)
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        # Idempotency: skip if this receipt was already recorded
        existing = Donation.query.filter_by(
            payment_provider="mpesa",
            provider_transaction_id=receipt_number,
        ).first()
        if existing:
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200

        # Match phone to a donor — best-effort; if not found, still record
        # the payment (admin can reconcile manually).
        donor = None
        if phone:
            normalized = mpesa_service._normalize_phone(phone)
            # Look for a saved M-Pesa payment method with this phone
            from server.models import PaymentMethod
            pm = PaymentMethod.query.filter_by(
                provider="mpesa",
                provider_payment_method_id=normalized,
            ).first()
            if pm:
                donor = pm.donor

        # We need a charity to record the donation against.
        # The account_reference we sent is "TW{charity_id}", parse it back.
        # If we can't determine it, skip DB recording but log it.
        account_ref = items.get("AccountReference", "")
        charity_id  = None
        if isinstance(account_ref, str) and account_ref.startswith("TW"):
            try:
                charity_id = int(account_ref[2:])
            except ValueError:
                pass

        if donor and charity_id:
            charity = Charity.query.get(charity_id)
            if charity and charity.status == "active":
                donation = Donation(
                    donor_id=donor.id,
                    charity_id=charity_id,
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

                # In-app notification for the donor
                db.session.add(Notification(
                    user_id=donor.user_id,
                    type="donation_successful",
                    title="M-Pesa donation confirmed",
                    message=(
                        f"Your M-Pesa payment of KES {amount:,.0f} "
                        f"to {charity.name} was received. "
                        f"Receipt: {receipt_number}"
                    ),
                    related_entity_type="donation",
                    related_entity_id=donation.id,
                ))
                db.session.commit()
                logger.info(
                    "Recorded M-Pesa donation: receipt=%s amount=%s charity=%s donor=%s",
                    receipt_number, amount, charity_id, donor.id,
                )
            else:
                logger.warning("Callback: charity %s not found or inactive", charity_id)
        else:
            logger.warning(
                "Callback: could not match donor (phone=%s) or charity (ref=%s) — "
                "receipt %s for KES %s needs manual reconciliation.",
                phone, account_ref, receipt_number, amount,
            )

    except Exception:
        logger.exception("Unhandled error in M-Pesa callback")
        # Still return 200 so Safaricom doesn't keep retrying
    
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
