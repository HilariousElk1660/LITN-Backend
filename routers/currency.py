from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services import currency_api

router = APIRouter(prefix="/currency", tags=["currency"])


@router.get("/latest")
async def latest(base: Optional[str] = Query("USD"), force_refresh: bool = Query(False)):
    """
    Return latest exchange rates from the configured provider.

    Query params:
    - base: base currency code (default: USD)
    - force_refresh: set true to bypass cache and fetch fresh rates

    Response:
    { base: "USD", rates: {"USD": 1.0, "GHS": 13.5, ...}, meta: {...}}
    """
    try:
        data = await currency_api.get_latest_rates(base_currency=base.upper(), force_refresh=force_refresh)
        return data
    except Exception as e:
        # don't return provider stack traces to clients
        raise HTTPException(status_code=502, detail=str(e))
