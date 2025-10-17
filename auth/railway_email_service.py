#!/usr/bin/env python3
"""
Railway Cloud Email Service - Fallback for SMTP-blocked environments
Provides immediate OTP delivery when traditional SMTP is unavailable
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class RailwayEmailService:
    """
    Email service designed for Railway and other cloud platforms that block SMTP
    Provides fallback OTP delivery methods when traditional email fails
    """
    
    def __init__(self):
        self.is_cloud_environment = self.detect_cloud_environment()
        self.log_file = "railway_email_fallback.log"
        
    def detect_cloud_environment(self):
        """Detect if running in a cloud environment that blocks SMTP"""
        cloud_indicators = [
            os.getenv('RAILWAY_ENVIRONMENT'),
            os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('RENDER_SERVICE_ID'),
            os.getenv('HEROKU_APP_NAME'),
            os.getenv('VERCEL_ENV'),
            os.path.exists('/app'),
            os.path.exists('/opt/render')
        ]
        
        detected = any(cloud_indicators)
        if detected:
            print("🌐 Railway/Cloud environment detected - Using fallback email service")
        
        return detected
    
    def send_otp_fallback(self, email, otp_code, user_name="User"):
        """
        Provide OTP via fallback method when SMTP is blocked
        Returns the OTP directly for immediate display to user
        """
        
        try:
            # Log the OTP for admin reference
            self.log_otp_attempt(email, otp_code, user_name)
            
            # In cloud environments, provide OTP directly
            if self.is_cloud_environment:
                print(f"🌐 Railway SMTP blocked - Providing OTP directly: {otp_code}")
                
                return {
                    'success': True,
                    'method': 'railway_fallback',
                    'otp_code': otp_code,
                    'message': f'Email services unavailable on Railway. Your login code is: {otp_code}',
                    'display_otp': True,
                    'cloud_environment': True
                }
            
            return {
                'success': False,
                'message': 'Email service not available'
            }
            
        except Exception as e:
            logger.error(f"Railway email service error: {e}")
            return {
                'success': False,
                'message': f'Fallback email service error: {e}'
            }
    
    def log_otp_attempt(self, email, otp_code, user_name):
        """Log OTP attempt for admin reference"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] OTP: {otp_code} | Email: {email} | User: {user_name} | Environment: Railway\n"
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
            print(f"📝 OTP logged to {self.log_file} for admin reference")
            
        except Exception as e:
            print(f"⚠️ Could not log OTP: {e}")
    
    def send_email_with_fallback(self, to_email, subject, body, otp_code=None):
        """
        Attempt email sending with Railway-aware fallback
        """
        
        # If we have an OTP code, use the fallback method
        if otp_code and self.is_cloud_environment:
            print(f"🌐 Railway environment - Using OTP fallback for {to_email}")
            return self.send_otp_fallback(to_email, otp_code)
        
        # For non-OTP emails in cloud environments, log and return info
        if self.is_cloud_environment:
            self.log_email_attempt(to_email, subject, body)
            return {
                'success': False,
                'message': 'Email services unavailable on Railway cloud platform',
                'cloud_environment': True,
                'fallback_content': body
            }
        
        return {
            'success': False,
            'message': 'Email service not configured for this environment'
        }
    
    def log_email_attempt(self, email, subject, body):
        """Log email attempt for admin reference"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"""
[{timestamp}] EMAIL ATTEMPT
To: {email}
Subject: {subject}
Body: {body[:200]}...
Environment: Railway
---
"""
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"⚠️ Could not log email attempt: {e}")

# Global instance
railway_email_service = RailwayEmailService()

def send_railway_otp(email, otp_code, user_name="User"):
    """Utility function for Railway OTP sending"""
    return railway_email_service.send_otp_fallback(email, otp_code, user_name)

def is_railway_environment():
    """Check if running in Railway environment"""
    return railway_email_service.is_cloud_environment
