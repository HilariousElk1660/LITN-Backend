from pydantic import BaseModel, EmailStr, Field

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=80)

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    id: str
    email: str
    display_name: str
    access_token: str
    token_type: str = "bearer"