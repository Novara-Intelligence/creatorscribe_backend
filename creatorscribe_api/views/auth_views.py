from ninja import NinjaAPI, File, Form
from ninja.files import UploadedFile
from ninja_jwt.tokens import AccessToken
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from typing import Optional
from ..authentication import AuthBearer
from ..schemas import (
    RegistrationRequestSchema,
    RegistrationResponseSchema,
    ErrorResponseSchema,
    SigninRequestSchema,
    SigninResponseSchema,
    OTPRequestSchema,
    OTPRequestResponseSchema,
    RegistrationVerificationRequestSchema,
    SigninVerificationRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetVerificationSchema,
    TokenResponseSchema,
    PasswordResetResponseSchema,
    OAuthSigninRequestSchema,
    OAuthSigninResponseSchema,
    LogoutRequestSchema,
    RefreshTokenRequestSchema,
    ProfileResponseSchema,
)
from ..models import OTPVerification
from ..models.client_models import Client
from ..services.email_service import EmailService

User = get_user_model()


# Initialize Django Ninja API for authentication
auth_api = NinjaAPI(version="1.0.0", title="CreatorScribe Authentication API", urls_namespace="auth")

@auth_api.post("/register", response={201: RegistrationResponseSchema, 400: ErrorResponseSchema})
def register_user(request, data: RegistrationRequestSchema):
    try:   
        # Check if verified user already exists
        existing_verified_user = User.objects.filter(email=data.email, is_verified=True).first()
        if existing_verified_user:
            return 400, {
                "success": False,
                "message": "A verified user with this email already exists. Please sign in instead."
            }
        
        # Handle unverified user - delete and allow re-registration
        existing_unverified_user = User.objects.filter(email=data.email, is_verified=False).first()
        if existing_unverified_user:
            # Clean up unverified user and their OTPs
            OTPVerification.objects.filter(user=existing_unverified_user).delete()
            existing_unverified_user.delete()
        
        # Create user within a transaction
        with transaction.atomic():
            user = User.objects.create_user(
                email=data.email,
                password=data.password,
                is_verified=False
            )
            
            # Generate OTP for registration
            otp = OTPVerification.generate_otp(user, otp_type='registration')
            
            # Send OTP via email (async/background - non-blocking)
            EmailService.send_otp_email_background(
                email=user.email,
                otp_code=otp.otp_code,
                otp_type='registration',
                full_name=user.full_name or user.email
            )
        
        # Return success response with OTP notification
        return 201, {
            "success": True,
            "message": f"OTP sent to {user.email}. Please verify OTP to complete registration."
        }
        
    except ValidationError as e:
        error_msg = str(e)
        if hasattr(e, 'message_dict'):
            # Extract first error message from validation errors
            error_msg = next(iter(e.message_dict.values()))[0] if e.message_dict else str(e)
        return 400, {
            "success": False,
            "message": f"Validation error: {error_msg}"
        }
    
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Registration failed: {str(e)}"
        }

@auth_api.post("/verify-registration", response={200: TokenResponseSchema, 400: ErrorResponseSchema})
def verify_registration_otp(request, data: RegistrationVerificationRequestSchema):
    try:
        # Debug prints
        print("---- VERIFY REGISTRATION DEBUG ----")
        print("Raw request body:", request.body)
        print("Parsed data:", data)
        print("Email:", data.email)
        print("OTP:", data.otp_code)

        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
            print("User found:", user)
        except User.DoesNotExist:
            print("User not found")
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }

        # Verify OTP
        is_valid, message = OTPVerification.verify_otp(user, data.otp_code, 'registration')
        print("OTP verification result:", is_valid, message)

        if not is_valid:
            return 400, {
                "success": False,
                "message": message
            }

        with transaction.atomic():
            user.is_verified = True
            user.last_login = timezone.now()
            user.save(update_fields=['is_verified', 'last_login'])
            print("User marked as verified")

            client = Client.objects.create(
                owner=user,
                client_name=user.username,
            )
            print("Client created:", client.id)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        print("Tokens generated")

        return 200, {
            "success": True,
            "message": "Registration completed successfully. You are now signed in.",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        }

    except Exception as e:
        print("Registration verification error:", str(e))
        return 400, {
            "success": False,
            "message": f"Registration verification failed: {str(e)}"
        }

@auth_api.post("/signin", response={200: TokenResponseSchema, 400: ErrorResponseSchema})
def signin_user(request, data: SigninRequestSchema):
    try:
        # Check if user exists
        try:
            user_check = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "Invalid email or password"
            }

        # Check if account verified
        if not user_check.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }

        # Authenticate user
        user = authenticate(request, email=data.email, password=data.password)

        if user is None:
            return 400, {
                "success": False,
                "message": "Invalid email or password"
            }

        # Check if active
        if not user.is_active:
            return 400, {
                "success": False,
                "message": "User account is deactivated"
            }

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return 200, {
            "success": True,
            "message": "Signin successful. Welcome back!",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        }

    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Signin failed: {str(e)}"
        }

@auth_api.post("/request-otp", response={200: OTPRequestResponseSchema, 400: OTPRequestResponseSchema})
def request_otp(request, data: OTPRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist",
            }
        
        # Validate OTP type
        if data.otp_type not in ['registration', 'password_reset']:
            return 400, {
                "success": False,
                "message": "Invalid OTP type. Must be 'registration' or 'password_reset'",
            }
        
        # Check verification status based on OTP type
        if data.otp_type == 'registration':
            if user.is_verified:
                return 400, {
                    "success": False,
                    "message": "User is already verified. Please sign in instead.",
                }
        else:  # signin or password_reset
            if not user.is_verified:
                return 400, {
                    "success": False,
                    "message": "Account not verified. Please complete registration first.",
                }
        
        # Generate OTP
        otp = OTPVerification.generate_otp(user, otp_type=data.otp_type)
        
        # Send OTP via email service (async/background - non-blocking)
        EmailService.send_otp_email_background(
            email=user.email,
            otp_code=otp.otp_code,
            otp_type=data.otp_type,
            full_name=user.full_name
        )
        
        return 200, {
            "success": True,
            "message": f"OTP sent to {data.email}. Please check your email.",
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Failed to send OTP: {str(e)}",
        }

@auth_api.post("/request-password-reset", response={200: PasswordResetResponseSchema, 400: ErrorResponseSchema})
def request_password_reset(request, data: PasswordResetRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Check if user is active
        if not user.is_active:
            return 400, {
                "success": False,
                "message": "User account is deactivated"
            }
        
        # Check if user is verified
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Generate OTP for password reset
        otp = OTPVerification.generate_otp(user, otp_type='password_reset')
        
        # Send OTP via email service (async/background - non-blocking)
        EmailService.send_otp_email_background(
            email=user.email,
            otp_code=otp.otp_code,
            otp_type='password_reset',
            full_name=user.full_name
        )
        
        return 200, {
            "success": True,
            "message": f"Password reset OTP sent to {user.email}. Please check your email."
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Failed to send password reset OTP: {str(e)}"
        }

@auth_api.post("/verify-password-reset", response={200: PasswordResetResponseSchema, 400: ErrorResponseSchema})
def verify_password_reset_otp(request, data: PasswordResetVerificationSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Check if user is verified
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Verify OTP for password reset
        is_valid, message = OTPVerification.verify_otp(user, data.otp_code, 'password_reset')
        
        if not is_valid:
            return 400, {
                "success": False,
                "message": message
            }
        
        # OTP verified successfully - update password
        user.set_password(data.new_password)
        user.save(update_fields=['password'])
        
        # Send password reset success email (async/background - non-blocking)
        EmailService.send_password_reset_success_email_background(
            email=user.email,
            full_name=user.full_name
        )
        
        return 200, {
            "success": True,
            "message": "Password reset successful. You can now sign in with your new password."
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Password reset verification failed: {str(e)}"
        }

@auth_api.post("/oauth-signin", response={200: OAuthSigninResponseSchema, 400: ErrorResponseSchema})
def oauth_signin(request, data: OAuthSigninRequestSchema):
    try:
        user = None
        
        # Try to find user by oauth_id first (most reliable for OAuth users)
        if data.oauth_id:
            try:
                user = User.objects.get(oauth_id=data.oauth_id)
            except User.DoesNotExist:
                pass
        
        # If not found by oauth_id, try by email
        if not user and data.email:
            try:
                user = User.objects.get(email=data.email)
            except User.DoesNotExist:
                pass
        
        # Create new user if doesn't exist
        if not user:
            with transaction.atomic():
                # Generate a random password for OAuth users (they won't use it)
                import secrets
                random_password = secrets.token_urlsafe(32)
                
                user = User.objects.create_user(
                    email=data.email,
                    password=random_password,
                    full_name=data.full_name,
                    oauth_provider=data.provider,
                    oauth_id=data.oauth_id,
                    oauth_access_token=data.access_token,
                    is_verified=True,  # OAuth users are automatically verified
                )
                
                # Create "Self as Client" automatically for new OAuth users
                Client.objects.create(
                    owner=user,
                    client_name=user.username,
                )
                
                # Update profile picture if provided
                if data.image:
                    # Note: In production, you might want to download and save the image
                    # For now, we'll just store the URL in a custom field or skip it
                    pass
        else:
            # Update existing user's OAuth info and last login
            user.oauth_provider = data.provider
            user.oauth_id = data.oauth_id
            user.oauth_access_token = data.access_token
            user.last_login = timezone.now()
            
            # If user wasn't verified before, mark as verified (OAuth verification)
            if not user.is_verified:
                user.is_verified = True
            
            # Update full name if it changed
            if data.full_name and data.full_name != user.full_name:
                user.full_name = data.full_name
            
            user.save(update_fields=['oauth_provider', 'oauth_id', 'oauth_access_token', 
                                     'last_login', 'is_verified', 'full_name'])
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        return 200, {
            "success": True,
            "message": "OAuth signin successful",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"OAuth signin failed: {str(e)}"
        }

@auth_api.post("/logout", response={200: ErrorResponseSchema, 400: ErrorResponseSchema})
def logout_user(request, data: LogoutRequestSchema):
    try:
        token = RefreshToken(data.refresh_token)
        token.blacklist()
        return 200, {"success": True, "message": "Logged out successfully."}
    except Exception as e:
        return 400, {"success": False, "message": f"Logout failed: {str(e)}"}

@auth_api.post("/refresh-token", response={200: TokenResponseSchema, 400: ErrorResponseSchema})
def refresh_token(request, data: RefreshTokenRequestSchema):
    try:
        refresh = RefreshToken(data.refresh_token)
        return 200, {
            "success": True,
            "message": "Token refreshed successfully.",
            "data": {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }
        }
    except Exception as e:
        return 400, {"success": False, "message": f"Token refresh failed: {str(e)}"}

@auth_api.get(
    "/profile",
    response={200: ProfileResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get authenticated user profile",
)
def get_profile(request):
    user = request.auth

    profile_pic_url = None
    if user.profile_pic:
        profile_pic_url = request.build_absolute_uri(user.profile_pic.url)

    days_left = None
    if user.subscription_type != 'free' and user.subscription_end_date:
        delta = user.subscription_end_date - timezone.now()
        days_left = max(0, delta.days)

    is_premium = user.is_premium()
    total_tokens = None if is_premium else user.get_monthly_token_limit()
    remaining_tokens = None if is_premium else user.get_remaining_tokens()

    return 200, {
        "success": True,
        "message": "Profile retrieved successfully",
        "data": {
            "profile_pic": profile_pic_url,
            "email": user.email,
            "full_name": user.full_name,
            "current_plan": "Premium" if is_premium else "Free",
            "days_left": days_left,
            "total_tokens": total_tokens,
            "remaining_tokens": remaining_tokens,
        }
    }


@auth_api.patch(
    "/profile",
    response={200: ProfileResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Update authenticated user's name and/or profile picture",
)
def edit_profile(
    request,
    full_name: Form[Optional[str]] = None,
    profile_pic: File[Optional[UploadedFile]] = None,
):
    user = request.auth

    if full_name is None and profile_pic is None:
        return 400, {"success": False, "message": "Provide at least one field to update (full_name or profile_pic)"}

    update_fields = []

    if full_name is not None:
        full_name = full_name.strip()
        if not full_name:
            return 400, {"success": False, "message": "full_name cannot be blank"}
        user.full_name = full_name
        update_fields.append('full_name')

    if profile_pic is not None:
        allowed_types = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
        if profile_pic.content_type not in allowed_types:
            return 400, {"success": False, "message": "Invalid image type. Allowed: jpeg, png, gif, webp"}
        # Delete old profile pic to avoid orphan files
        if user.profile_pic:
            user.profile_pic.delete(save=False)
        user.profile_pic = profile_pic
        update_fields.append('profile_pic')

    user.save(update_fields=update_fields)

    profile_pic_url = None
    if user.profile_pic:
        profile_pic_url = request.build_absolute_uri(user.profile_pic.url)

    days_left = None
    if user.subscription_type != 'free' and user.subscription_end_date:
        delta = user.subscription_end_date - timezone.now()
        days_left = max(0, delta.days)

    return 200, {
        "success": True,
        "message": "Profile updated successfully",
        "data": {
            "profile_pic": profile_pic_url,
            "email": user.email,
            "full_name": user.full_name,
            "current_plan": "Premium" if user.is_premium() else "Free",
            "days_left": days_left,
        }
    }
