import os
import hmac
import hashlib
import json
from typing import Optional
import httpx

# Airtel payment service helper
# Purpose: encapsulate HTTP calls to the Airtel payment API and related helpers
# - initiate_payment: starts a payment request with Airtel
# - verify_signature: verify webhook signatures using a configured secret

AIRTEL_API_URL = os.getenv("AIRTEL_API_URL")  # e.g. https://openapi.airtel.africa/v1/merchant/transactions
AIRTEL_API_KEY = os.getenv("AIRTEL_API_KEY")
AIRTEL_CALLBACK_SECRET = os.getenv("AIRTEL_CALLBACK_SECRET")  # used to verify callback signatures


async def initiate_payment(amount: int, currency: str, phone_number: str, reference: str, callback_url: str) -> dict:
    """
    Initiate a payment with Airtel.

    Parameters:
    - amount: integer amount in the smallest currency unit (e.g., cents)
    - currency: currency code like "USD" or "GHS"
    - phone_number: customer's phone number in international format
    - reference: merchant reference to correlate payment with internal records
    - callback_url: URL Airtel will call with payment result

    Returns the parsed JSON response from the Airtel API.

    Note: This function uses httpx.AsyncClient for non-blocking requests.
    """

    if not AIRTEL_API_URL or not AIRTEL_API_KEY:
        raise RuntimeError("Airtel API configuration missing (AIRTEL_API_URL/AIRTEL_API_KEY)")

    payload = {
        "amount": str(amount),
        "currency": currency,
        "customer_msisdn": phone_number,
        "merchant_reference": reference,
        "callback_url": callback_url,
    }

    headers = {
        "Authorization": f"Bearer {AIRTEL_API_KEY}",
        "Content-Type": "application/json",
    }

    # Use an async HTTP client for the request so it can be awaited in FastAPI handlers
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(AIRTEL_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def verify_signature(body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify the webhook signature sent by Airtel.

    Many payment providers sign the callback payload using an HMAC with a shared secret.
    This helper computes the HMAC-SHA256 of the raw body and compares it to the header.

    - body: raw request body bytes
    - signature_header: value from the incoming request header (e.g. "X-Airtel-Signature")

    Returns True when the signature matches, False otherwise.
    """
    if not AIRTEL_CALLBACK_SECRET or not signature_header:
        return False

    computed = hmac.new(
        AIRTEL_CALLBACK_SECRET.encode("utf-8"), body, digestmod=hashlib.sha256
    ).hexdigest()

    # Use hmac.compare_digest for timing-attack resistant comparison
    return hmac.compare_digest(computed, signature_header)
