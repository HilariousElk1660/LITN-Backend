from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from core.database import get_connection
from core.security import hash_password, verify_password, create_access_token, get_current_user
from services.email_service import send_email
from schemas.auth import (
    SignupRequest,
    SigninRequest,
    ProfileUpdateRequest,
    PasswordChangeRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    AuthResponse,
)
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/sign_up", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(payload: SignupRequest):
    password_hash = hash_password(payload.password)

    async with get_connection() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO users (fullname, email, password, role)
                VALUES ($1, $2, $3, 'reader')
                RETURNING user_id, fullname, email, role
                """,
                payload.fullname,
                payload.email.lower(),
                password_hash,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    token = create_access_token(str(row["user_id"]), row["email"], row["role"])

    return AuthResponse(
        user_id=str(row["user_id"]),
        email=row["email"],
        fullname=row["fullname"],
        role=row["role"],
        access_token=token,
    )

@router.post("/sign_in", response_model=AuthResponse)
async def sign_in(payload: SigninRequest):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id, fullname, email, password, role
            FROM users
            WHERE email = $1
            """,
            payload.email.lower(),
        )

    # Same message for "not found" and "wrong password" — don't leak which it was
    if row is None or not verify_password(payload.password, row["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(str(row["user_id"]), row["email"], row["role"])

    return AuthResponse(
        user_id=str(row["user_id"]),
        email=row["email"],
        fullname=row["fullname"],
        role=row["role"],
        access_token=token,
    )

@router.patch("/profile", response_model=AuthResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    async with get_connection() as conn:
        try:
            row = await conn.fetchrow(
                """
                UPDATE users
                SET fullname = $1, email = $2
                WHERE user_id = $3
                RETURNING user_id, fullname, email, role
                """,
                payload.fullname,
                payload.email.lower(),
                current_user["user_id"],
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # email/fullname changed — issue a fresh token so the JWT payload stays accurate
    token = create_access_token(str(row["user_id"]), row["email"], row["role"])

    return AuthResponse(
        user_id=str(row["user_id"]),
        email=row["email"],
        fullname=row["fullname"],
        role=row["role"],
        access_token=token,
        token_type="bearer",
    )


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT password FROM users WHERE user_id = $1",
            current_user["user_id"],
        )

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        try:
            valid = verify_password(payload.current_password, row["password"])
        except ValueError:
            valid = False

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        new_hash = hash_password(payload.password)
        await conn.execute(
            "UPDATE users SET password = $1 WHERE user_id = $2",
            new_hash,
            current_user["user_id"],
        )


@router.post("/forgot_password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(payload: ForgotPasswordRequest):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, fullname, email FROM users WHERE email = $1",
            payload.email.lower(),
        )

        # Always return 204 to avoid disclosing whether the email exists
        if row is None:
            return

        token = uuid.uuid4().hex
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await conn.execute(
            "INSERT INTO password_resets (token, user_id, expires_at) VALUES ($1, $2, $3)",
            token,
            row["user_id"],
            expires_at,
        )

    # Build reset link and send email (do outside DB transaction)
    reset_link = payload.redirect_url or ""
    if reset_link and "?" in reset_link:
        reset_link = f"{reset_link}&token={token}"
    else:
        reset_link = f"{reset_link}?token={token}"

    send_email(row["email"], "reset_password", user_name=row.get("fullname", "Reader"), reset_url=reset_link)


@router.post("/reset_password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT token, user_id, expires_at FROM password_resets WHERE token = $1",
            payload.token,
        )

        if row is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token.")

        if row["expires_at"] < datetime.now(timezone.utc):
            # cleanup expired token
            await conn.execute("DELETE FROM password_resets WHERE token = $1", payload.token)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token.")

        new_hash = hash_password(payload.password)
        await conn.execute(
            "UPDATE users SET password = $1 WHERE user_id = $2",
            new_hash,
            row["user_id"],
        )

        # Remove used token
        await conn.execute("DELETE FROM password_resets WHERE token = $1", payload.token)