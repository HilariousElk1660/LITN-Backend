from fastapi import APIRouter, HTTPException, status
import asyncpg

from core.database import get_connection
from core.security import hash_password, verify_password, create_access_token
from schemas.auth import SignupRequest, SigninRequest, AuthResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
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

    return AuthResponse(
        id=str(row["id"]),
        email=row["email"],
        display_name=row["display_name"],
        access_token=token,
    )

@router.post("/signin", response_model=AuthResponse)
async def signin(payload: SigninRequest):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, display_name, password_hash
            FROM users
            WHERE email = $1
            """,
            payload.email.lower(),
        )

    # Same error for "no such user" and "wrong password" — don't leak which one it was
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(str(row["id"]), row["email"])

    return AuthResponse(
        id=str(row["id"]),
        email=row["email"],
        display_name=row["display_name"],
        access_token=token,
    )