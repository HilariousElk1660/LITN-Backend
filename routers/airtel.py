from fastapi import APIRouter, Request, Depends, HTTPException, status
from typing import Any
from core.database import get_connection
from core.security import get_current_user
from services import airtel_service
from schemas.payment import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    AirtelCallbackPayload,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/airtel/initiate", response_model=InitiatePaymentResponse)
async def initiate_airtel_payment(payload: InitiatePaymentRequest, current_user: dict | None = Depends(get_current_user)) -> Any:
    """
    Initiate an Airtel payment.

    - This endpoint prepares a payment with Airtel and returns the provider response.
    - 'reference' should map to an internal record (for example a book_request id) so the webhook
      can later mark the corresponding record as paid when the callback arrives.

    Note: current_user is optional but recommended; including it ties the payment to an authenticated user.
    """

    # Build a callback URL where Airtel will POST the payment result.
    # This should be reachable publicly (use env config / reverse proxy in production).
    # For now the callback URL is read from an env var or falls back to a sensible default.
    callback_url = airtel_service.AIRTEL_API_URL and "" or ""  # placeholder, not used here

    try:
        # Initiate payment with Airtel service helper
        resp = await airtel_service.initiate_payment(
            amount=payload.amount,
            currency=payload.currency,
            phone_number=payload.phone_number,
            reference=payload.reference,
            callback_url=payload.reference,  # merchant should replace with real callback; keep reference for correlation
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return InitiatePaymentResponse(success=True, data=resp, message="Airtel initiation response")


@router.post("/airtel/webhook")
async def airtel_webhook(request: Request):
    """
    Endpoint to receive Airtel payment callbacks/webhooks.

    Responsibilities:
    - Verify the webhook's signature using the configured callback secret
    - Parse the payload and update internal records (e.g., set book_requests.status = 'paid')

    The exact webhook shape depends on Airtel product/region; this handler implements a generic
    approach and should be adapted if Airtel's callback differs from what the project expects.
    """

    body = await request.body()
    signature = request.headers.get("X-Airtel-Signature")

    # Verify signature to ensure callback authenticity
    if not airtel_service.verify_signature(body, signature):
        # Unauthorized or malformed callback
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload_json = await request.json()

    # Basic normalization for expected fields (merchant_reference, status)
    merchant_reference = payload_json.get("merchant_reference") or payload_json.get("reference")
    status = payload_json.get("status") or payload_json.get("transaction_status")

    if not merchant_reference:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing merchant reference")

    # Example: update a book_requests record to mark payment as 'paid' when status indicates success
    async with get_connection() as conn:
        if status and status.lower() in ("success", "completed", "paid"):
            # Update record matching the merchant_reference
            await conn.execute(
                "UPDATE book_requests SET status = $1 WHERE request_id = $2",
                "paid",
                merchant_reference,
            )
        else:
            # If payment failed or pending, store status for later inspection
            await conn.execute(
                "UPDATE book_requests SET status = $1 WHERE request_id = $2",
                status or "failed",
                merchant_reference,
            )

    # Respond with 200 OK to acknowledge receipt
    return {"ok": True}
