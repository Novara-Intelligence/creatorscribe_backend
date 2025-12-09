"""
Email service for sending OTP and other emails
Uses background thread pool for non-blocking email sending
"""
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for background email sending
email_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix='email_worker')


class EmailService:
    """Service class for background email operations"""
    
    @staticmethod
    def _generate_otp_html(context: dict) -> str:
        """Generate HTML content for OTP email"""
        otp_type = context['otp_type']
        otp_code = context['otp_code']
        full_name = context['full_name']
        
        # Title text based on OTP type
        title_map = {
            'registration': 'Your Registration OTP',
            'signin': 'Your Sign-in OTP',
            'password_reset': 'Your Password Reset OTP'
        }
        title = title_map.get(otp_type, 'Your new OTP created successfully')
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>OTP Verification</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
        
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                    background-color: #F4F5F7;
                    color: #172B4D;
                    line-height: 1.6;
                    padding: 20px;
                }}
        
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                }}
        
                .header {{
                    border-bottom: 1px solid #E5E7EB;
                    padding: 24px;
                    text-align: center;
                }}
        
                .logo-container {{
                    display: inline-flex;
                    justify-content: center;
                    align-items: center;
                    gap: 8px;
                }}
        
                .logo {{
                    width: 32px;
                    height: 32px;
                    display: block;
                }}
        
                .brand-name {{ 
                    font-weight: 600;
                    font-size: 18px;
                    display: block;
                    margin-left: 8px;
                }}
        
                .content {{
                    padding: 16px;
                }}
        
                .title {{
                    font-size: 18px;
                    font-weight: 600;
                    text-align: center;
                    margin: 16px 0;
                }}
        
                .greeting {{
                    font-size: 14px;
                    margin: 8px 0;
                    font-weight: 600;
                }}
        
                .text {{
                    font-size: 14px;
                    margin: 8px 0;
                }}
        
                .otp-box {{
                    margin: 16px 0;
                    border: 1px solid #E5E7EB;
                    padding: 16px;
                    border-radius: 8px;
                    text-align: center;
                }}
        
                .otp-label {{
                    font-weight: 600;
                    margin-bottom: 8px;
                }}
        
                .otp-code {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #0055CC;
                    letter-spacing: 0.1em;
                    margin: 8px 0;
                }}
        
                .otp-expiry {{
                    font-size: 12px;
                    color: #666;
                }}
        
                .security-section {{
                    margin: 16px 0;
                }}
        
                .security-title {{
                    font-weight: 600;
                    font-size: 14px;
                    margin-bottom: 8px;
                }}
        
                .instructions-list {{
                    list-style-type: disc;
                    margin: 8px 0;
                    padding-left: 32px;
                }}
        
                .instructions-list li {{
                    font-size: 14px;
                    margin: 4px 0;
                }}
        
                .signature {{
                    font-size: 14px;
                    margin: 8px 0;
                }}
        
                .footer {{
                    padding: 16px;
                    border-top: 1px solid #E5E7EB;
                    text-align: center;
                }}
        
                .footer-text {{
                    font-size: 14px;
                    color: #666;
                    margin: 0 0 8px 0;
                    display: block;
                }}
        
                .footer-brand {{
                    font-weight: 600;
                    font-size: 14px;
                    color: #6B7280;
                    margin: 0;
                    display: block;
                }}
            </style>
        </head>
        
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo-container">
                        <img src="https://raw.githubusercontent.com/dhineshio/icons/main/cs_logo.png" alt="Creator Scribe Logo"
                            class="logo">
                        <p class="brand-name">Creator Scribe</p>
                    </div>
                </div>
        
                <div class="content">
                    <h1 class="title">{title}</h1>
                    <p class="greeting">Hi {full_name},</p>
                    <p class="text">
                        You recently requested an OTP. This code can be used to access your account and perform authenticated
                        operations, and as such should be kept secret.
                    </p>
                    <div class="otp-box">
                        <div class="otp-label">Your OTP Code</div>
                        <div class="otp-code">{otp_code}</div>
                        <div class="otp-expiry">This code will expire in 15 minutes</div>
                    </div>
        
                    <div class="security-section">
                        <p class="security-title">Did not request this change?</p>
                        <p class="text">
                            If you did not request this action you should immediately:
                        </p>
                        <ol class="instructions-list">
                            <li>Visit your security settings and revoke the OTP.</li>
                            <li>Change you creator scribe account password.</li>
                        </ol>
                    </div>
        
                    <p class="signature">
                        Cheers,<br>
                        The Creator Scribe Team
                    </p>
                </div>
                <div class="footer">
                    <p class="footer-text">This message was sent to you by creatorscribe</p>
                    <p class="footer-brand">CREATORSCRIBE</p>
                </div>
            </div>
        </body>
        
        </html>
        """
        return html_content
    
    @staticmethod
    def _send_otp_email_sync(email: str, otp_code: str, otp_type: str, full_name: str = None) -> bool:
        """
        Internal synchronous method for sending OTP email
        Used by both sync and async versions
        """
        try:
            # Determine subject and message based on OTP type
            subject_map = {
                'registration': 'Complete Your Registration - OTP Verification',
                'signin': 'Sign In Verification - OTP Code',
                'password_reset': 'Password Reset - OTP Verification'
            }
            
            subject = subject_map.get(otp_type, 'OTP Verification')
            
            # Create email context
            context = {
                'otp_code': otp_code,
                'otp_type': otp_type,
                'full_name': full_name or 'User',
                'email': email,
            }
            
            # Generate HTML content
            html_content = EmailService._generate_otp_html(context)
            
            # Send email
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroone.com')
            
            # Create email message
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=from_email,
                to=[email]
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()
            
            logger.info(f"OTP email sent successfully to {email} for {otp_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def _send_welcome_email_sync(email: str, full_name: str) -> bool:
        """Internal synchronous method for sending welcome email"""
        try:
            subject = 'Welcome to Creator Scribe!'
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to Creator Scribe</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
            
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                        background-color: #F4F5F7;
                        color: #172B4D;
                        line-height: 1.6;
                        padding: 20px;
                    }}
            
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                        border-radius: 8px;
                        overflow: hidden;
                    }}
            
                    .header {{
                        border-bottom: 1px solid #E5E7EB;
                        padding: 24px;
                        text-align: center;
                    }}
            
                    .logo-container {{
                        display: inline-flex;
                        justify-content: center;
                        align-items: center;
                        gap: 8px;
                    }}
            
                    .logo {{
                        width: 32px;
                        height: 32px;
                        display: block;
                    }}
            
                    .brand-name {{
                        font-weight: 600;
                        font-size: 18px;
                        display: block;
                        margin-left: 8px;
                    }}
            
                    .content {{
                        padding: 16px;
                    }}
            
                    .title {{
                        font-size: 18px;
                        font-weight: 600;
                        text-align: center;
                        margin: 16px 0;
                    }}
            
                    .greeting {{
                        font-size: 14px;
                        margin: 8px 0;
                        font-weight: 600;
                    }}
            
                    .text {{
                        font-size: 14px;
                        margin: 8px 0;
                    }}
            
                    .welcome-box {{
                        margin: 16px 0;
                        border: 1px solid #E5E7EB;
                        padding: 16px;
                        border-radius: 8px;
                        background-color: #F9FAFB;
                    }}
            
                    .signature {{
                        font-size: 14px;
                        margin: 8px 0;
                    }}
            
                    .footer {{
                        padding: 16px;
                        border-top: 1px solid #E5E7EB;
                        text-align: center;
                    }}
            
                    .footer-text {{
                        font-size: 14px;
                        color: #666;
                        margin: 0 0 8px 0;
                        display: block;
                    }}
            
                    .footer-brand {{
                        font-weight: 600;
                        font-size: 14px;
                        color: #6B7280;
                        margin: 0;
                        display: block;
                    }}
                </style>
            </head>
            
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo-container">
                            <img src="https://raw.githubusercontent.com/dhineshio/icons/main/cs_logo.png" alt="Creator Scribe Logo"
                                class="logo">
                            <p class="brand-name">Creator Scribe</p>
                        </div>
                    </div>
            
                    <div class="content">
                        <h1 class="title">Welcome to Creator Scribe! 🎉</h1>
                        <p class="greeting">Hi {full_name},</p>
                        <p class="text">
                            Welcome to Creator Scribe! Your account has been successfully created and verified.
                        </p>
                        <div class="welcome-box">
                            <p class="text">
                                We're excited to have you on board. You can now access all features of your account and start creating amazing content.
                            </p>
                        </div>
                        <p class="text">
                            If you have any questions or need assistance, feel free to reach out to our support team.
                        </p>
                        <p class="signature">
                            Cheers,<br>
                            The Creator Scribe Team
                        </p>
                    </div>
                    <div class="footer">
                        <p class="footer-text">This message was sent to you by creatorscribe</p>
                        <p class="footer-brand">CREATORSCRIBE</p>
                    </div>
                </div>
            </body>
            
            </html>
            """
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroone.com')
            
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=from_email,
                to=[email]
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()
            
            logger.info(f"Welcome email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def _send_password_reset_success_email_sync(email: str, full_name: str) -> bool:
        """Internal synchronous method for sending password reset success email"""
        try:
            subject = 'Password Reset Successful'
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Password Reset Successful</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
            
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                        background-color: #F4F5F7;
                        color: #172B4D;
                        line-height: 1.6;
                        padding: 20px;
                    }}
            
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                        border-radius: 8px;
                        overflow: hidden;
                    }}
            
                    .header {{
                        border-bottom: 1px solid #E5E7EB;
                        padding: 24px;
                        text-align: center;
                    }}
            
                    .logo-container {{
                        display: inline-flex;
                        justify-content: center;
                        align-items: center;
                        gap: 8px;
                    }}
            
                    .logo {{
                        width: 32px;
                        height: 32px;
                        display: block;
                    }}
            
                    .brand-name {{
                        font-weight: 600;
                        font-size: 18px;
                        display: block;
                        margin-left: 8px;
                    }}
            
                    .content {{
                        padding: 16px;
                    }}
            
                    .title {{
                        font-size: 18px;
                        font-weight: 600;
                        text-align: center;
                        margin: 16px 0;
                    }}
            
                    .greeting {{
                        font-size: 14px;
                        margin: 8px 0;
                        font-weight: 600;
                    }}
            
                    .text {{
                        font-size: 14px;
                        margin: 8px 0;
                    }}
            
                    .success-box {{
                        margin: 16px 0;
                        border: 1px solid #10B981;
                        padding: 16px;
                        border-radius: 8px;
                        background-color: #ECFDF5;
                    }}
            
                    .success-title {{
                        font-weight: 600;
                        color: #059669;
                        margin-bottom: 8px;
                    }}
            
                    .security-section {{
                        margin: 16px 0;
                        background-color: #FEF3C7;
                        border: 1px solid #F59E0B;
                        padding: 16px;
                        border-radius: 8px;
                    }}
            
                    .security-title {{
                        font-weight: 600;
                        font-size: 14px;
                        margin-bottom: 8px;
                        color: #D97706;
                    }}
            
                    .signature {{
                        font-size: 14px;
                        margin: 8px 0;
                    }}
            
                    .footer {{
                        padding: 16px;
                        border-top: 1px solid #E5E7EB;
                        text-align: center;
                    }}
            
                    .footer-text {{
                        font-size: 14px;
                        color: #666;
                        margin: 0 0 8px 0;
                        display: block;
                    }}
            
                    .footer-brand {{
                        font-weight: 600;
                        font-size: 14px;
                        color: #6B7280;
                        margin: 0;
                        display: block;
                    }}
                </style>
            </head>
            
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo-container">
                            <img src="https://raw.githubusercontent.com/dhineshio/icons/main/cs_logo.png" alt="Creator Scribe Logo"
                                class="logo">
                            <p class="brand-name">Creator Scribe</p>
                        </div>
                    </div>
            
                    <div class="content">
                        <h1 class="title">Password Reset Successful ✅</h1>
                        <p class="greeting">Hi {full_name},</p>
                        <div class="success-box">
                            <p class="success-title">Your password has been successfully reset.</p>
                            <p class="text">
                                You can now sign in to your account using your new password.
                            </p>
                        </div>
                        <div class="security-section">
                            <p class="security-title">Did not perform this action?</p>
                            <p class="text">
                                If you did not reset your password, please contact our support team immediately to secure your account.
                            </p>
                        </div>
                        <p class="signature">
                            Cheers,<br>
                            The Creator Scribe Team
                        </p>
                    </div>
                    <div class="footer">
                        <p class="footer-text">This message was sent to you by creatorscribe</p>
                        <p class="footer-brand">CREATORSCRIBE</p>
                    </div>
                </div>
            </body>
            
            </html>
            """
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroone.com')
            
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=from_email,
                to=[email]
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()
            
            logger.info(f"Password reset success email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset success email to {email}: {str(e)}")
            return False
    
    # ==================== BACKGROUND METHODS ====================
    
    @staticmethod
    def send_otp_email_background(email: str, otp_code: str, otp_type: str, full_name: str = None) -> None:
        """
        Fire-and-forget: Send OTP email in background without waiting for result
        This is the fastest option - returns immediately
        
        Args:
            email: Recipient email address
            otp_code: The OTP code to send
            otp_type: Type of OTP (registration, signin, password_reset)
            full_name: User's full name (optional)
        """
        email_executor.submit(
            EmailService._send_otp_email_sync,
            email,
            otp_code,
            otp_type,
            full_name
        )
        logger.info(f"OTP email queued for background sending to {email}")
    
    @staticmethod
    def send_welcome_email_background(email: str, full_name: str) -> None:
        """
        Fire-and-forget: Send welcome email in background without waiting for result
        
        Args:
            email: Recipient email address
            full_name: User's full name
        """
        email_executor.submit(
            EmailService._send_welcome_email_sync,
            email,
            full_name
        )
        logger.info(f"Welcome email queued for background sending to {email}")
    
    @staticmethod
    def send_password_reset_success_email_background(email: str, full_name: str) -> None:
        """
        Fire-and-forget: Send password reset success email in background
        
        Args:
            email: Recipient email address
            full_name: User's full name
        """
        email_executor.submit(
            EmailService._send_password_reset_success_email_sync,
            email,
            full_name
        )
        logger.info(f"Password reset success email queued for background sending to {email}")