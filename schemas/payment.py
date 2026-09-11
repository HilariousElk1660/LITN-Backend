from pydantic import BaseModel

class CreatePaymentRequest(BaseModel):
    order_id: str
    amount: float
    item_name: str
    buyer_email: str | None = None
    request_id: str | None = None
    book_id: str | None = None
    reader_id: str | None = None
    reader_email: str | None = None
    reader_name: str | None = None

class CreatePaymentResponse(BaseModel):
    redirect_url: str