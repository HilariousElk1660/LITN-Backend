import re
import uuid
from typing import Any

import requests

from core.airtel import (
    AIRTEL_BASE_URL,
    AIRTEL_CLIENT_ID,
    AIRTEL_CLIENT_SECRET,
    AIRTEL_COUNTRY,
    AIRTEL_CURRENCY,
)


def normalize_phone_number(phone_number: str) -> str:
    digits = re.sub(r"\D", "", str(phone_number or ""))
    if not digits:
        return digits
    if digits.startswith("256"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits


def build_auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def build_collection_payload(
    amount: str | int | float,
    phone_number: str,
    reference: str,
    description: str = "Payment collection",
    transaction_id: str | None = None,
    country: str | None = None,
    currency: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_country = (country or AIRTEL_COUNTRY or "UG").upper()
    safe_currency = (currency or AIRTEL_CURRENCY or "UGX").upper()
    safe_reference = reference or transaction_id or str(uuid.uuid4())
    safe_transaction_id = transaction_id or str(uuid.uuid4())

    payload: dict[str, Any] = {
        "reference": safe_reference,
        "subscriber": {
            "country": safe_country,
            "currency": safe_currency,
            "msisdn": normalize_phone_number(phone_number),
        },
        "transaction": {
            "amount": str(amount),
            "country": safe_country,
            "currency": safe_currency,
            "id": safe_transaction_id,
        },
        "description": description or "Payment collection",
    }

    if metadata:
        payload["metadata"] = metadata

    return payload


def request_access_token() -> str:
    if not AIRTEL_CLIENT_ID or not AIRTEL_CLIENT_SECRET:
        raise RuntimeError("Airtel Money client credentials are not configured.")

    url = f"{AIRTEL_BASE_URL}/auth/oauth2/token"
    response = requests.post(
        url,
        headers={"Content-Type": "application/json", "Accept": "*/*"},
        json={
            "client_id": AIRTEL_CLIENT_ID,
            "client_secret": AIRTEL_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )

    try:
        body = response.json()
    except ValueError:
        body = {"message": response.text}

    if response.status_code != 200 or not body.get("access_token"):
        raise RuntimeError(
            f"Airtel token request failed ({response.status_code}): {body.get('message', body)}"
        )

    return body["access_token"]


def collect_airtel_money(
    amount: str | int | float,
    phone_number: str,
    reference: str,
    description: str = "Payment collection",
    transaction_id: str | None = None,
    country: str | None = None,
    currency: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        access_token = request_access_token()
    except RuntimeError:
        raise

    country_code = (country or AIRTEL_COUNTRY or "UG").upper()
    currency_code = (currency or AIRTEL_CURRENCY or "UGX").upper()
    payload = build_collection_payload(
        amount=amount,
        phone_number=phone_number,
        reference=reference,
        description=description,
        transaction_id=transaction_id,
        country=country_code,
        currency=currency_code,
        metadata=metadata,
    )

    url = f"{AIRTEL_BASE_URL}/merchant/v1/payments/"
    headers = build_auth_headers(access_token)
    headers.update({"X-Country": country_code, "X-Currency": currency_code})

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    try:
        body = response.json()
    except ValueError:
        body = {"message": response.text}

    if response.status_code != 200:
        return {
            "success": False,
            "status_code": response.status_code,
            "data": body,
            "reference": reference,
            "transaction_id": payload["transaction"]["id"],
        }

    return {
        "success": True,
        "status_code": response.status_code,
        "data": body,
        "reference": reference,
        "transaction_id": payload["transaction"]["id"],
    }


def check_collection_status(transaction_id: str, country: str | None = None, currency: str | None = None) -> dict[str, Any]:
    try:
        access_token = request_access_token()
    except RuntimeError:
        raise

    url = f"{AIRTEL_BASE_URL}/standard/v1/payments/{transaction_id}"
    headers = build_auth_headers(access_token)
    headers.update({"X-Country": (country or AIRTEL_COUNTRY or "UG").upper(), "X-Currency": (currency or AIRTEL_CURRENCY or "UGX").upper()})

    response = requests.get(url, headers=headers, timeout=30)

    try:
        body = response.json()
    except ValueError:
        body = {"message": response.text}

    return {
        "success": response.status_code == 200,
        "status_code": response.status_code,
        "data": body,
    }


def get_transaction_status(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return "UNKNOWN"

    if "status" in payload:
        return str(payload["status"]).upper()

    data = payload.get("data")
    if isinstance(data, dict):
        transaction = data.get("transaction") or data
        if isinstance(transaction, dict):
            return str(transaction.get("status", "UNKNOWN")).upper()

    transaction = payload.get("transaction")
    if isinstance(transaction, dict):
        return str(transaction.get("status", "UNKNOWN")).upper()

    return "UNKNOWN"
