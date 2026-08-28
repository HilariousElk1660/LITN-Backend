from pydantic import BaseModel
from typing import Optional

# Pydantic schemas for payment endpoints

class InitiatePaymentRequest(BaseModel):
    # amount in the smallest currency unit (e.g., cents)
    amount: int
    currency: str
    phone_number: str
    # internal reference used to correlate with DB records (e.g., book_request id)
    reference: str


class InitiatePaymentResponse(BaseModel):
    # passthrough of Airtel response (may include transaction id, status, redirect url, etc.)
    success: bool
    data: Optional[dict]
    message: Optional[str]


class AirtelCallbackPayload(BaseModel):
    # Generic callback shape. Airtel's real webhook may differ by region/product
    merchant_reference: str
    transaction_id: Optional[str]
    status: str
    amount: Optional[str]
    currency: Optional[str]
    customer_msisdn: Optional[str]
    raw: Optional[dict] = None
