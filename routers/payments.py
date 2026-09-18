import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.payfast import PAYFAST_URL
from routers.admin import Update_book_request, apply_book_request_update
from schemas.payment import CreatePaymentRequest, CreatePaymentResponse
from services.airtel_service import (
    check_collection_status,
    collect_airtel_money,
    get_transaction_status,
)
from services.payfast_service import build_payment_data, generate_signature

router = APIRouter(prefix="/payments", tags=["payments"])


class AirtelCollectionRequest(BaseModel):
    amount: float | str
    phone_number: str
    reference: str | None = None
    description: str | None = None
    request_id: str | None = None
    book_id: str | None = None
    reader_id: str | None = None
    reader_email: str | None = None
    reader_name: str | None = None
    transaction_id: str | None = None


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
        lang=payload.lang,
    )
    query_string = urllib.parse.urlencode(data)
    return {"redirect_url": f"{PAYFAST_URL}?{query_string}"}


@router.post("/airtel/collect")
async def airtel_collect(payload: AirtelCollectionRequest):
    metadata = {}
    if payload.request_id:
        metadata["request_id"] = payload.request_id
    if payload.book_id:
        metadata["book_id"] = payload.book_id
    if payload.reader_id:
        metadata["reader_id"] = payload.reader_id
    if payload.reader_email:
        metadata["reader_email"] = payload.reader_email
    if payload.reader_name:
        metadata["reader_name"] = payload.reader_name

    reference = payload.reference or payload.request_id or payload.transaction_id
    if not reference:
        reference = f"litn-{uuid.uuid4().hex[:12]}"
    elif payload.request_id and not payload.reference:
        reference = f"{payload.request_id}:{payload.book_id or 'book'}:{payload.reader_id or 'reader'}"

    result = collect_airtel_money(
        amount=payload.amount,
        phone_number=payload.phone_number,
        reference=reference,
        description=payload.description or "Book purchase payment",
        transaction_id=payload.transaction_id,
        metadata=metadata or None,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    return result


@router.get("/airtel/status/{transaction_id}")
async def airtel_status(transaction_id: str):
    return check_collection_status(transaction_id)


@router.post("/airtel/callback")
async def airtel_callback(request: Request):
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    status = get_transaction_status(payload)
    if status in {"TS", "SUCCESS", "SUCCESSFUL", "200"}:
        metadata: dict = {}
        if isinstance(payload.get("metadata"), dict):
            metadata = payload["metadata"]
        elif isinstance(payload.get("data"), dict):
            data = payload["data"]
            if isinstance(data.get("metadata"), dict):
                metadata = data["metadata"]
            elif isinstance(data.get("transaction"), dict):
                metadata = data["transaction"].get("metadata") or {}

        request_id = metadata.get("request_id") or metadata.get("requestId")
        reference = payload.get("reference") or (payload.get("data", {}).get("reference") if isinstance(payload.get("data"), dict) else None)
        if not request_id and isinstance(reference, str) and ":" in reference:
            request_id = reference.split(":", 1)[0]

        if request_id:
            book_id = metadata.get("book_id") or ""
            reader_id = metadata.get("reader_id") or ""
            reader_email = metadata.get("reader_email") or ""
            reader_name = metadata.get("reader_name") or ""

            payment_update = Update_book_request(
                request_id=str(request_id),
                status="paid",
                book_id=str(book_id),
                reader_id=str(reader_id),
                reader_email=str(reader_email),
                reader_name=str(reader_name),
                payment_type="airtel",
            )
            await apply_book_request_update(payment_update)

    return {"status": "ok", "transaction_status": status}


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