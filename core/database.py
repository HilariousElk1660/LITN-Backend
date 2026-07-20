from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager
import asyncpg
from dotenv import load_dotenv 

load_dotenv()

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        statement_cache_size=0,  # required for Neon's pooled connection string
    )

async def close_db_pool():
    if pool:
        await pool.close()

@asynccontextmanager
async def get_connection():
    async with pool.acquire() as conn:
        yield conn