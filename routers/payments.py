from fastapi import APIRouter, Request, HTTPException
from core.payfast import PAYFAST_URL
from services.payfast_service import build_payment_data, generate_signature
from schemas.payment import CreatePaymentRequest, CreatePaymentResponse
from routers.admin import apply_book_request_update, Update_book_request
import urllib.parse

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(payload: CreatePaymentRequest):
    data = build_payment_data(
        order_id=payload.order_id,
        amount=payload.amount,
        item_name=payload.item_name,
        buyer_email=payload.buyer_email,
        request_id=payload.request_id,
        book_id=payload.book_id,
        reader_id=payload.reader_id,
        reader_email=payload.reader_email,
        reader_name=payload.reader_name,
        lang=payload.lang
    )
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

    if data.get("payment_status") == "COMPLETE":
        payload = Update_book_request(
            request_id=data.get("custom_str1"),
            status="paid",
            book_id=data.get("custom_str2"),
            reader_id=data.get("custom_str3"),
            reader_email=data.get("custom_str4"),
            reader_name=data.get("custom_str5"),
            payment_type="payfast",
        )
        await apply_book_request_update(payload)

    return {"status": "ok"}