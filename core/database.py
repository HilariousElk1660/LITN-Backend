from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager
import asyncpg
from dotenv import load_dotenv 

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    if pool is not None and not getattr(pool, "_closed", False):
        await pool.close()
    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        statement_cache_size=0,  # required for Neon's pooled connection string
    )

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        pool = None

@asynccontextmanager
async def get_connection():
    global pool

    if pool is None or getattr(pool, "_closed", False):
        await init_db_pool()

    try:
        async with pool.acquire() as conn:
            yield conn
    except (asyncpg.exceptions.ConnectionDoesNotExistError, RuntimeError):
        # Pool may have been closed during a hot reload or app shutdown while a
        # background task was still running.
        await init_db_pool()
        async with pool.acquire() as conn:
            yield conn
        
        
        PAYFAST_MERCHANT_ID = os.environ["PAYFAST_MERCHANT_ID"]
PAYFAST_MERCHANT_KEY = os.environ["PAYFAST_MERCHANT_KEY"]
PAYFAST_PASSPHRASE = os.environ.get("PAYFAST_PASSPHRASE", "")
PAYFAST_MODE = os.environ.get("PAYFAST_MODE", "sandbox")

PAYFAST_URL = (
    "https://sandbox.payfast.co.za/eng/process"
    if PAYFAST_MODE == "sandbox"
    else "https://www.payfast.co.za/eng/process"
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")

VALID_PAYFAST_IPS = [
    "197.97.145.144",
    "197.97.145.145",
    "41.74.179.194",
    "196.33.227.184",
    "196.33.227.185",
    "197.221.32.68",
]
