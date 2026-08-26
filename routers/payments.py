from fastapi import APIRouter, Request, HTTPException
from core.payfast import PAYFAST_URL, VALID_PAYFAST_IPS
from services.payfast_service import build_payment_data, generate_signature
from schemas.payment import CreatePaymentRequest, CreatePaymentResponse
from core.database import get_connection

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(payload: CreatePaymentRequest):
    data = build_payment_data(
        order_id=payload.order_id,
        amount=payload.amount,
        item_name=payload.item_name,
        buyer_email=payload.buyer_email,
    )
    import urllib.parse
    query_string = urllib.parse.urlencode(data)
    return {"redirect_url": f"{PAYFAST_URL}?{query_string}"}


@router.post("/notify")
async def payfast_notify(request: Request):
    form = await request.form()
    data = dict(form)

    received_signature = data.pop("signature", None)
    expected_signature = generate_signature(data)

    if received_signature != expected_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    client_ip = request.client.host
    if client_ip not in VALID_PAYFAST_IPS:
        raise HTTPException(status_code=400, detail="Invalid source IP")

    if data.get("payment_status") == "COMPLETE":
        order_id = data.get("m_payment_id")
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE orders SET status = 'paid' WHERE id = $1", order_id
            )

    return {"status": "ok"}