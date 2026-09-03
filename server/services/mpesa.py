"""
server/services/mpesa.py — Safaricom Daraja API integration

Handles:
  - OAuth2 access token (cached for its lifetime)
  - STK Push (Lipa Na M-Pesa Online / Express)
  - STK Push Query (poll for payment result)

Environment variables required (set in Render dashboard or .env):
    MPESA_CONSUMER_KEY       — from Safaricom Developer portal
    MPESA_CONSUMER_SECRET    — from Safaricom Developer portal
    MPESA_SHORTCODE          — Business shortcode (Paybill or Till)
    MPESA_PASSKEY            — Lipa Na M-Pesa Online passkey
    MPESA_CALLBACK_URL       — Public HTTPS URL Safaricom posts results to
                               e.g. https://your-app.onrender.com/api/mpesa/callback
    MPESA_ENV                — "sandbox" (default) or "production"
"""

import os
import base64
import hashlib
import time
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (filled from environment — leave blank here, set in Render)
# ---------------------------------------------------------------------------
CONSUMER_KEY    = os.environ.get("MPESA_CONSUMER_KEY", "")
CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "")
SHORTCODE       = os.environ.get("MPESA_SHORTCODE", "174379")          # Daraja sandbox default
PASSKEY         = os.environ.get("MPESA_PASSKEY", "")
CALLBACK_URL    = os.environ.get("MPESA_CALLBACK_URL", "")
MPESA_ENV       = os.environ.get("MPESA_ENV", "sandbox")               # "sandbox" | "production"

# Daraja base URLs
_BASE = {
    "sandbox":    "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

def _base_url() -> str:
    return _BASE.get(MPESA_ENV, _BASE["sandbox"])

# ---------------------------------------------------------------------------
# Simple in-process token cache (survives multiple requests in one process)
# ---------------------------------------------------------------------------
_token_cache: dict = {"token": None, "expires_at": 0}


def _get_access_token() -> str:
    """Return a valid Daraja OAuth2 access token, refreshing if expired."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["token"]

    if not CONSUMER_KEY or not CONSUMER_SECRET:
        raise RuntimeError(
            "MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET must be set "
            "in environment variables before M-Pesa calls can be made."
        )

    credentials = base64.b64encode(
        f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()
    ).decode()

    resp = requests.get(
        f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {credentials}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _token_cache["token"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_password() -> tuple[str, str]:
    """
    Return (password, timestamp) for the STK push request.
    password = base64(shortcode + passkey + timestamp)
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{SHORTCODE}{PASSKEY}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def _normalize_phone(phone: str) -> str:
    """
    Convert any common Kenyan phone format to the 254XXXXXXXXX format
    Daraja requires.

    Accepts: 0712345678 / +254712345678 / 254712345678 / 712345678
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    if not phone.startswith("254"):
        phone = "254" + phone
    return phone


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def stk_push(phone: str, amount: int, account_reference: str, description: str) -> dict:
    """
    Initiate a Lipa Na M-Pesa Online (STK Push) request.

    Args:
        phone            — donor's Safaricom number (any common format)
        amount           — integer amount in KES (Daraja rejects decimals)
        account_reference— short label shown on donor's phone (max 12 chars)
        description      — transaction description (max 13 chars)

    Returns the raw Daraja JSON response, which includes:
        MerchantRequestID, CheckoutRequestID, ResponseCode,
        ResponseDescription, CustomerMessage

    Raises requests.HTTPError on HTTP errors, RuntimeError on config issues.
    """
    token = _get_access_token()
    password, timestamp = _generate_password()
    phone_normalized = _normalize_phone(phone)

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password":          password,
        "Timestamp":         timestamp,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            int(amount),          # must be integer
        "PartyA":            phone_normalized,
        "PartyB":            SHORTCODE,
        "PhoneNumber":       phone_normalized,
        "CallBackURL":       CALLBACK_URL,
        "AccountReference":  account_reference[:12],
        "TransactionDesc":   description[:13],
    }

    resp = requests.post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def stk_query(checkout_request_id: str) -> dict:
    """
    Query the status of a previous STK push by its CheckoutRequestID.

    Returns the raw Daraja JSON.  Key fields to check:
        ResultCode   "0"  → payment confirmed
                     "1032" → request cancelled by user
                     "1037" → timeout
                     other  → failure
    """
    token = _get_access_token()
    password, timestamp = _generate_password()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password":          password,
        "Timestamp":         timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    resp = requests.post(
        f"{_base_url()}/mpesa/stkpushquery/v1/query",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
