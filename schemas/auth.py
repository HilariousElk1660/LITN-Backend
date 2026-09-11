from pydantic import BaseModel, EmailStr, Field

class SignupRequest(BaseModel):
    fullname: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class SigninRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)

class ProfileUpdateRequest(BaseModel):
    fullname: str
    email: EmailStr

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(max_length=72)
    password: str = Field(min_length=8, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    redirect_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)

class AuthResponse(BaseModel):
    user_id: str
    email: str
    fullname: str
    role: str
    access_token: str
    token_type: str = "bearer"