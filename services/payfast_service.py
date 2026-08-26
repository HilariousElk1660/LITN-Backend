import hashlib
import urllib.parse
from core.payfast import PAYFAST_PASSPHRASE

def generate_signature(data: dict) -> str:
    pairs = []
    for key, value in data.items():
        if value is None or value == "":
            continue
        pairs.append(f"{key}={urllib.parse.quote_plus(str(value))}")

    param_string = "&".join(pairs)

    if PAYFAST_PASSPHRASE:
        param_string += f"&passphrase={urllib.parse.quote_plus(PAYFAST_PASSPHRASE)}"

    return hashlib.md5(param_string.encode()).hexdigest()


def build_payment_data(order_id: str, amount: float, item_name: str, buyer_email: str | None = None) -> dict:
    from core.payfast import (
        PAYFAST_MERCHANT_ID,
        PAYFAST_MERCHANT_KEY,
        FRONTEND_URL,
        BACKEND_URL,
    )

    data = {
        "merchant_id": PAYFAST_MERCHANT_ID,
        "merchant_key": PAYFAST_MERCHANT_KEY,
        "return_url": f"{FRONTEND_URL}/payment/success",
        "cancel_url": f"{FRONTEND_URL}/payment/cancelled",
        "notify_url": f"{BACKEND_URL}/payments/notify",
        "m_payment_id": order_id,
        "amount": f"{amount:.2f}",
        "item_name": item_name,
    }
    if buyer_email:
        data["email_address"] = buyer_email

    data["signature"] = generate_signature(data)
    return data