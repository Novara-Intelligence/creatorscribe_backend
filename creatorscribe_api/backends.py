"""
Custom email backend to handle SSL certificate issues
"""
import ssl
import smtplib
from django.core.mail.backends.smtp import EmailBackend as BaseEmailBackend
from django.conf import settings


class SSLEmailBackend(BaseEmailBackend):
    """
    Custom SMTP email backend that handles SSL certificate verification issues
    """
    
    def open(self):
        """
        Override the open method to use a custom SSL context
        that's more permissive with certificate verification
        """
        if self.connection:
            return False
        
        try:
            # Create SSL context that's more permissive
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create SMTP connection
            self.connection = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            
            # Enable debug if needed
            if not self.fail_silently:
                self.connection.set_debuglevel(1)
            
            if self.use_tls:
                self.connection.starttls(context=ssl_context)
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
            
        except Exception as e:
            if not self.fail_silently:
                raise
            return False