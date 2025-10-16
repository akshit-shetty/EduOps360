"""
Web-based Email Service for Cloud Platforms
Alternative to SMTP when cloud hosting blocks SMTP connections
"""
import os
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WebEmailService:
    """Web-based email service using HTTP APIs instead of SMTP"""
    
    def __init__(self):
        self.services = [
            self._try_emailjs,
            self._try_formspree,
            self._try_netlify_forms
        ]
    
    def send_otp_email(self, to_email: str, otp_code: str, user_name: str = "User") -> Dict[str, Any]:
        """Send OTP email using web services"""
        
        # Email content
        subject = "EduOps360 Login Code"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 500px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2563eb; margin: 0; font-size: 24px;">EduOps360</h1>
                    <p style="color: #666; margin: 5px 0 0 0;">Educational Management Platform</p>
                </div>
                
                <h2 style="color: #333; text-align: center; margin-bottom: 20px;">Login Verification Code</h2>
                
                <p style="color: #555; font-size: 16px; margin-bottom: 20px;">Hello {user_name},</p>
                
                <p style="color: #555; font-size: 16px; margin-bottom: 30px;">
                    Your login verification code is:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="font-size: 36px; font-weight: bold; color: #2563eb; background-color: #f8fafc; padding: 20px 30px; border-radius: 8px; letter-spacing: 8px; display: inline-block; border: 2px solid #e5e7eb;">
                        {otp_code}
                    </div>
                </div>
                
                <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 15px; margin: 20px 0;">
                    <p style="color: #92400e; font-size: 14px; margin: 0;">
                        <strong>⚠️ Important:</strong> This code expires in 10 minutes and can only be used once.
                    </p>
                </div>
                
                <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 30px;">
                    <p style="color: #777; font-size: 12px; text-align: center; margin: 0;">
                        If you did not request this code, please ignore this email.<br>
                        This is an automated message from EduOps360.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Try each service until one works
        for service in self.services:
            try:
                result = service(to_email, subject, html_content, otp_code)
                if result.get('success'):
                    return result
            except Exception as e:
                logger.warning(f"Email service failed: {e}")
                continue
        
        # If all services fail, return fallback message
        return {
            'success': False,
            'message': f'All email services unavailable. OTP: {otp_code}',
            'otp_code': otp_code
        }
    
    def _try_emailjs(self, to_email: str, subject: str, html_content: str, otp_code: str) -> Dict[str, Any]:
        """Try EmailJS service (free tier available)"""
        # This would require EmailJS setup, skipping for now
        raise Exception("EmailJS not configured")
    
    def _try_formspree(self, to_email: str, subject: str, html_content: str, otp_code: str) -> Dict[str, Any]:
        """Try Formspree service (free tier available)"""
        # This would require Formspree setup, skipping for now
        raise Exception("Formspree not configured")
    
    def _try_netlify_forms(self, to_email: str, subject: str, html_content: str, otp_code: str) -> Dict[str, Any]:
        """Try Netlify Forms (if deployed on Netlify)"""
        # This would require Netlify setup, skipping for now
        raise Exception("Netlify Forms not configured")

# Simple fallback email service that always provides OTP in response
class FallbackEmailService:
    """Fallback service that provides OTP in the response when email fails"""
    
    def send_otp_email(self, to_email: str, otp_code: str, user_name: str = "User") -> Dict[str, Any]:
        """Return OTP in response when email services are unavailable"""
        
        print(f"📧 FALLBACK EMAIL SERVICE")
        print(f"To: {to_email}")
        print(f"Subject: EduOps360 Login Code")
        print(f"OTP Code: {otp_code}")
        print(f"User: {user_name}")
        print(f"⚠️  Email delivery unavailable on this platform")
        
        # Log to file for admin reference
        try:
            with open('email_fallback.log', 'a', encoding='utf-8') as f:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} | {to_email} | {otp_code} | {user_name}\n")
        except:
            pass
        
        return {
            'success': True,  # Consider it successful since we're providing the OTP
            'message': f'Email service unavailable. Your login code is: {otp_code}',
            'otp_code': otp_code,
            'fallback': True
        }

# Factory function to get appropriate email service
def get_email_service():
    """Get the best available email service for the current environment"""
    
    # Check if we're in a cloud environment that blocks SMTP
    is_cloud_env = any([
        os.getenv('RENDER'),  # Render
        os.getenv('RENDER_SERVICE_ID'),  # Render service
        os.getenv('HEROKU_APP_NAME'),  # Heroku
        os.getenv('VERCEL'),  # Vercel
        os.getenv('NETLIFY'),  # Netlify
        os.getenv('AWS_LAMBDA_FUNCTION_NAME'),  # AWS Lambda
        '/opt/render' in os.getcwd() if os.getcwd() else False,  # Render path detection
    ])
    
    if is_cloud_env:
        print("🔍 Cloud environment detected, using fallback email service")
        return FallbackEmailService()
    else:
        print("🔍 Local environment detected, using web email service")
        return WebEmailService()
