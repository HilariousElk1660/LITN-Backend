from pydantic import BaseModel, EmailStr, Field

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    fullname: str = Field(min_length=1, max_length=80)

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user_id: str
    email: str
    fullname: str
    role: str
    access_token: str
    token_type: str = "bearer"