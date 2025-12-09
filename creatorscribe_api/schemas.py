from ninja import Schema
from typing import Optional, List
from datetime import datetime

# Common Schemas
class ErrorResponseSchema(Schema):
    success: bool = False
    message: str

# Registration Schemas
class RegistrationRequestSchema(Schema):
    full_name: str
    email: str
    password: str
    phone_number: Optional[str] = None

class RegistrationResponseSchema(Schema):
    success: bool
    message: str

# Registration Verification Schemas
class RegistrationVerificationRequestSchema(Schema):
    email: str
    otp_code: str

# Signin Schemas
class SigninRequestSchema(Schema):
    email: str
    password: str

class SigninResponseSchema(Schema):
    success: bool
    message: str

# Signin Verification Schemas
class SigninVerificationRequestSchema(Schema):
    email: str
    otp_code: str

# OTP Response Schemas
class TokenResponseSchema(Schema):
    success: bool
    message: str
    access_token: str
    refresh_token: str

# Request OTP Manual Schema ( Resend OTP / Manually trigger a otp)
class OTPRequestSchema(Schema):
    email: str
    otp_type: str = "registration"  # registration, signin, password_reset

class OTPRequestResponseSchema(Schema):
    success: bool
    message: str

# Password Reset Schema
class PasswordResetRequestSchema(Schema):
    email: str

class PasswordResetVerificationSchema(Schema):
    email: str
    otp_code: str
    new_password: str

class PasswordResetResponseSchema(Schema):
    success: bool
    message: str

# OAuth Signin Schema
class OAuthSigninRequestSchema(Schema):
    provider: str
    email: str
    full_name: str
    image: Optional[str] = None
    oauth_id: str
    access_token: str

class OAuthSigninResponseSchema(Schema):
    success: bool
    access_token: str
    refresh_token: str

# Client Schemas
class ClientCreateRequestSchema(Schema):
    client_name: str
    contact_person: str
    contact_email: str
    contact_phone: Optional[str] = None
    industry_type: str = "other"
    brand_logo: Optional[str] = None  # Base64 encoded image or file path
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    preferred_post_time: Optional[str] = None  # Format: "HH:MM"

class ClientCreateResponseSchema(Schema):
    success: bool
    message: str
    data: "ClientResponseSchema"

class ClientResponseSchema(Schema):
    id: int
    client_name: str
    contact_person: str
    contact_email: str
    contact_phone: Optional[str] = None
    industry_type: str
    brand_logo: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    preferred_post_time: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ClientListResponseSchema(Schema):
    success: bool
    message: str
    data: List[ClientResponseSchema]
    count: int


