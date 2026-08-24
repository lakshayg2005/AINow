from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class VerifyEmailResponse(BaseModel):
    message: str
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    message: str

class CurrentUserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_email_verified: bool

class VerifyEmailResponse(BaseModel):
    message: str
    email: EmailStr

class ResendVerificationResponse(BaseModel):
    message: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr