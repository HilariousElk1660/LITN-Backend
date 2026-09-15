import hashlib
import urllib.parse
from core.payfast import PAYFAST_PASSPHRASE, PAYFAST_MERCHANT_ID, PAYFAST_MERCHANT_KEY, FRONTEND_URL, BACKEND_URL

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


def build_payment_data(
    order_id: str,
    amount: float,
    item_name: str,
    buyer_email: str | None = None,
    request_id: str | None = None,
    book_id: str | None = None,
    reader_id: str | None = None,
    reader_email: str | None = None,
    reader_name: str | None = None,
    lang: str | None = "en"
) -> dict:
    return_params = {}
    if request_id:
        return_params["request_id"] = request_id
    if book_id:
        return_params["book_id"] = book_id
    if reader_id:
        return_params["reader_id"] = reader_id
    if reader_email:
        return_params["reader_email"] = reader_email
    if reader_name:
        return_params["reader_name"] = reader_name

    return_url = f"{FRONTEND_URL}/{lang}/payment/success"
    if return_params:
        return_url += f"?{urllib.parse.urlencode(return_params)}"

    data = {
        "merchant_id": PAYFAST_MERCHANT_ID,
        "merchant_key": PAYFAST_MERCHANT_KEY,
        "return_url": return_url,
        "cancel_url": f"{FRONTEND_URL}/{lang}/payment/cancelled",
        "notify_url": f"{BACKEND_URL}/payments/notify",
        "m_payment_id": order_id,
        "amount": f"{amount:.2f}",
        "item_name": item_name,
    }
    if buyer_email:
        data["email_address"] = buyer_email

    # Pass our own metadata through PayFast so the webhook (server-to-server)
    # gets it back too — the return_url only reaches the browser, not PayFast's own server-side notify call.
    if request_id:
        data["custom_str1"] = request_id
    if book_id:
        data["custom_str2"] = book_id
    if reader_id:
        data["custom_str3"] = reader_id
    if reader_email:
        data["custom_str4"] = reader_email
    if reader_name:
        data["custom_str5"] = reader_name

    data["signature"] = generate_signature(data)
    return data