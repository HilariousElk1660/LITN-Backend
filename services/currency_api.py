import os
import time
from typing import Dict, Any
import httpx

# CurrencyAPI integration helper (reads API key from env CURRENCY_API_KEY)
# - get_latest_rates(base_currency): returns normalized mapping of currency -> numeric rate
# - caches results in memory for CACHE_TTL_SECONDS

CURRENCY_API_KEY = os.getenv("CURRENCY_API_KEY")
CURRENCY_API_URL = os.getenv("CURRENCY_API_URL", "https://api.currencyapi.net/v3/latest")
CACHE_TTL_SECONDS = int(os.getenv("CURRENCY_CACHE_TTL", "3600"))

_cache: Dict[str, Any] = {"ts": 0, "base": None, "result": None}


async def _fetch_from_provider(base_currency: str = "USD") -> Dict[str, Any]:
    if not CURRENCY_API_KEY:
        raise RuntimeError("CURRENCY_API_KEY environment variable is not set")

    params = {"apikey": CURRENCY_API_KEY, "base_currency": base_currency}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(CURRENCY_API_URL, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_latest_rates(base_currency: str = "USD", force_refresh: bool = False) -> Dict[str, Any]:
    """
    Return a dict: { base: str, rates: { 'USD': 1.0, 'GHS': 13.5, ... }, meta: ... }
    Uses a short in-memory cache to limit calls.
    """
    now = int(time.time())
    if not force_refresh and _cache["result"] and _cache["base"] == base_currency and now - _cache["ts"] < CACHE_TTL_SECONDS:
        return _cache["result"]

    payload = await _fetch_from_provider(base_currency)

    # CurrencyAPI v3 returns `data` mapping currencies to { code, value }
    data = payload.get("data") or {}
    normalized = {}
    for code, item in data.items():
        try:
            # item may be {"code":"USD","value":1}
            if isinstance(item, dict) and "value" in item:
                normalized[code] = float(item["value"])
            else:
                normalized[code] = float(item)
        except Exception:
            continue

    result = {"base": base_currency, "rates": normalized, "meta": payload.get("meta")}

    _cache.update({"ts": now, "base": base_currency, "result": result})
    return result
