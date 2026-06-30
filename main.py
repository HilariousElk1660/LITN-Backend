from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from contextlib import asynccontextmanager
import asyncpg

from database import init_db_pool, close_db_pool, get_connection
from auth import hash_password, create_access_token

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=80)

class SignupResponse(BaseModel):
    id: str
    email: str
    display_name: str
    access_token: str
    token_type: str = "bearer"

@app.post("/auth/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):
    password_hash = hash_password(payload.password)

    async with get_connection() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, password_hash, display_name)
                VALUES ($1, $2, $3)
                RETURNING id, email, display_name
                """,
                payload.email.lower(),
                password_hash,
                payload.display_name,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    token = create_access_token(str(row["id"]), row["email"])

    return SignupResponse(
        id=str(row["id"]),
        email=row["email"],
        display_name=row["display_name"],
        access_token=token,
    )