from pydantic import BaseModel

class CreatePaymentRequest(BaseModel):
    order_id: str
    amount: float
    item_name: str
    buyer_email: str | None = None

class CreatePaymentResponse(BaseModel):
    redirect_url: str