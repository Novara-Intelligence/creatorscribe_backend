from ninja import Schema
from typing import Optional


class ErrorResponseSchema(Schema):
    success: bool = False
    message: str


class RegistrationRequestSchema(Schema):
    email: str
    password: str


class RegistrationResponseSchema(Schema):
    success: bool
    message: str


class RegistrationVerificationRequestSchema(Schema):
    email: str
    otp_code: str


class SigninRequestSchema(Schema):
    email: str
    password: str


class SigninResponseSchema(Schema):
    success: bool
    message: str


class SigninVerificationRequestSchema(Schema):
    email: str
    otp_code: str


class TokenDataSchema(Schema):
    access_token: str
    refresh_token: str


class TokenResponseSchema(Schema):
    success: bool
    message: str
    data: TokenDataSchema


class OTPRequestSchema(Schema):
    email: str
    otp_type: str = "registration"  # registration, password_reset


class OTPRequestResponseSchema(Schema):
    success: bool
    message: str


class PasswordResetRequestSchema(Schema):
    email: str


class PasswordResetVerificationSchema(Schema):
    email: str
    otp_code: str
    new_password: str


class PasswordResetResponseSchema(Schema):
    success: bool
    message: str


class OAuthSigninRequestSchema(Schema):
    provider: str
    email: str
    full_name: str
    image: Optional[str] = None
    oauth_id: str
    access_token: str


class OAuthSigninResponseSchema(Schema):
    success: bool
    message: str
    data: TokenDataSchema


class LogoutRequestSchema(Schema):
    refresh_token: str


class ProfileDataSchema(Schema):
    profile_pic: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    current_plan: str
    days_left: Optional[int] = None


class ProfileResponseSchema(Schema):
    success: bool
    message: str
    data: ProfileDataSchema
