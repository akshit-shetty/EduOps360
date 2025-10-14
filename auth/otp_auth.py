#!/usr/bin/env python3
"""
OTP Authentication System for EduOps360
Email-based One-Time Password authentication
"""

import secrets
import string
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from auth.email_utils import send_smtp_email
from auth.email_config import get_email_accounts
from utils.database import get_db_connection, get_db_cursor, execute_query
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OTPAuthenticator:
    """OTP-based authentication system"""
    
    def __init__(self):
        self.otp_expiry_minutes = 10  # OTP expires in 10 minutes
        self.setup_otp_table()
    
    def setup_otp_table(self):
        """Create OTP table for storing temporary codes"""
        create_sql = '''
            CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                attempts INTEGER DEFAULT 0
            )
        '''
        execute_query(create_sql)
    
    def generate_otp(self, length=6):
        """Generate a random OTP code"""
        # Use digits only for simplicity
        characters = string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    
    def send_simple_otp(self, email, otp_code, user_name="User"):
        """Simple OTP logging - No console spam"""
        # Only save to file for reference, no console output
        try:
            with open('otp_codes.txt', 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} | {email} | {otp_code}\n")
        except:
            pass
        
        return True

    def send_otp_email(self, email, otp_code, user_name="User", account_key="primary"):
        """Send OTP via email - with comprehensive debugging"""
        try:
            print(f"🔍 Starting OTP email send to {email}")
            
            subject = "EduOps360 Login Code"
            
            # Simple, clean HTML that's less likely to be flagged as spam
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 500px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px;">
                    <h2 style="color: #333; text-align: center; margin-bottom: 30px;">EduOps360 Login Code</h2>
                    
                    <p style="color: #555; font-size: 16px;">Hello {user_name},</p>
                    
                    <p style="color: #555; font-size: 16px;">
                        Your login verification code is:
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <div style="font-size: 32px; font-weight: bold; color: #007bff; background-color: #f8f9fa; padding: 15px 25px; border-radius: 5px; letter-spacing: 5px; display: inline-block;">
                            {otp_code}
                        </div>
                    </div>
                    
                    <p style="color: #555; font-size: 14px;">
                        This code expires in 10 minutes and can only be used once.
                    </p>
                    
                    <p style="color: #777; font-size: 12px; margin-top: 30px;">
                        If you did not request this code, please ignore this email.
                    </p>
                </div>
            </body>
            </html>
            """
            
            print(f"🔍 Calling send_smtp_email with account_key: {account_key}")
            
            # Send email using SMTP directly
            result = send_smtp_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                account_key=account_key
            )
            
            print(f"🔍 send_smtp_email returned: {result}")
            
            # Check if result is a dict (new format) or boolean (old format)
            if isinstance(result, dict):
                success = result.get('success', False)
                message = result.get('message', 'Unknown error')
                print(f"🔍 Email result - Success: {success}, Message: {message}")
            else:
                success = bool(result)
                print(f"🔍 Email result (boolean): {success}")
            
            if success:
                print(f"✅ OTP sent successfully to {email}")
                # Also log to file as backup (for admin reference only)
                self.send_simple_otp(email, otp_code, user_name)
                return True
            else:
                print(f"❌ Failed to send OTP to {email}")
                # Still log to file even if email fails
                self.send_simple_otp(email, otp_code, user_name)
                return False
                
        except Exception as e:
            print(f"❌ Error sending OTP email: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_otp(self, email, account_key="primary"):
        """Create and send OTP for user"""
        # Check if user exists
        if not self.user_exists(email):
            return False, "User not found"
        
        # Clean up old OTPs for this email
        self.cleanup_old_otps(email)
        
        # Generate new OTP
        otp_code = self.generate_otp()
        expires_at = datetime.now() + timedelta(minutes=self.otp_expiry_minutes)
        
        try:
            # Store OTP in database
            execute_query('''
                INSERT INTO otp_codes (email, otp_code, expires_at)
                VALUES (?, ?, ?)
            ''', (email, otp_code, expires_at))
            
            # Get user name for personalized email
            user_data = execute_query('''
                SELECT first_name, last_name FROM users WHERE email = ?
            ''', (email,), fetch='one')
            
            if user_data and user_data.get('first_name'):
                user_name = f"{user_data['first_name']} {user_data.get('last_name', '') or ''}".strip()
            else:
                user_name = "User"
            
            # Send OTP via email with timeout handling
            try:
                import threading
                import time
                
                # Create a result container
                email_result = {'success': False, 'message': ''}
                
                def send_email_async():
                    try:
                        result = self.send_otp_email(email, otp_code, user_name, account_key)
                        email_result['success'] = result
                        email_result['message'] = 'Email sent' if result else 'Email failed'
                    except Exception as e:
                        email_result['success'] = False
                        email_result['message'] = f'Email error: {e}'
                
                # Start email sending in background thread
                email_thread = threading.Thread(target=send_email_async)
                email_thread.daemon = True
                email_thread.start()
                
                # Wait up to 20 seconds for email to send
                email_thread.join(timeout=20)
                
                if email_thread.is_alive():
                    # Email is still sending, but return success since OTP is stored
                    logger.warning(f"Email sending taking longer than expected for {email}")
                    # For testing - log OTP to file
                    self.send_simple_otp(email, otp_code, user_name)
                    return True, f"OTP generated successfully. Email is being sent in background. [TEST: OTP is {otp_code}]"
                elif email_result['success']:
                    return True, "OTP sent successfully"
                else:
                    # For testing - log OTP to file and show in message
                    self.send_simple_otp(email, otp_code, user_name)
                    return True, f"OTP generated successfully. Email delivery may be delayed. [TEST: OTP is {otp_code}]"
                    
            except Exception as e:
                logger.error(f"Error in async email sending: {e}")
                return True, "OTP generated successfully. Email delivery may be delayed."
                
        except Exception as e:
            print(f"❌ Error creating OTP: {e}")
            return False, "Error generating OTP"
    
    def verify_otp(self, email, otp_code):
        """Verify OTP code"""
        try:
            # Find valid OTP
            otp_data = execute_query('''
                SELECT id, expires_at, attempts FROM otp_codes 
                WHERE email = ? AND otp_code = ? AND is_used = FALSE
                ORDER BY created_at DESC LIMIT 1
            ''', (email, otp_code), fetch='one')
            
            if not otp_data:
                return False, "Invalid OTP code"
            
            otp_id = otp_data['id']
            expires_at = otp_data['expires_at']
            attempts = otp_data['attempts']
            
            # Check if OTP has expired
            expires_datetime = datetime.fromisoformat(expires_at)
            if datetime.now() > expires_datetime:
                # Mark as used
                execute_query('''
                    UPDATE otp_codes SET is_used = TRUE WHERE id = ?
                ''', (otp_id,))
                return False, "OTP has expired"
            
            # Check attempt limit (max 3 attempts)
            if attempts >= 3:
                execute_query('''
                    UPDATE otp_codes SET is_used = TRUE WHERE id = ?
                ''', (otp_id,))
                return False, "Too many attempts. Please request a new OTP"
            
            # Mark OTP as used
            execute_query('''
                UPDATE otp_codes SET is_used = TRUE WHERE id = ?
            ''', (otp_id,))
            
            return True, "OTP verified successfully"
            
        except Exception as e:
            print(f"❌ Error verifying OTP: {e}")
            return False, "Error verifying OTP"
    
    def increment_otp_attempts(self, email, otp_code):
        """Increment failed attempts for OTP"""
        execute_query('''
            UPDATE otp_codes 
            SET attempts = attempts + 1 
            WHERE email = ? AND otp_code = ? AND is_used = FALSE
        ''', (email, otp_code))
    
    def user_exists(self, email):
        """Check if user exists in database"""
        user = execute_query('SELECT id FROM users WHERE email = ?', (email,), fetch='one')
        return user is not None
    
    def get_user_info(self, email):
        """Get user information after successful OTP verification"""
        user_data = execute_query('''
            SELECT id, first_name, last_name, email, role, is_active 
            FROM users WHERE email = ?
        ''', (email,), fetch='one')
        
        if user_data:
            return {
                'id': user_data['id'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'email': user_data['email'],
                'role': user_data['role'],
                'is_active': user_data['is_active']
            }
        return None
    
    def cleanup_old_otps(self, email=None):
        """Clean up expired or old OTP codes"""
        if email:
            # Clean up old OTPs for specific email
            execute_query('''
                DELETE FROM otp_codes 
                WHERE email = ? AND (expires_at < ? OR is_used = TRUE)
            ''', (email, datetime.now()))
        else:
            # Clean up all expired OTPs
            execute_query('''
                DELETE FROM otp_codes 
                WHERE expires_at < ? OR is_used = TRUE
            ''', (datetime.now(),))
    
    def get_otp_stats(self):
        """Get OTP statistics for monitoring"""
        # Total OTPs generated today
        today_result = execute_query('''
            SELECT COUNT(*) as count FROM otp_codes 
            WHERE DATE(created_at) = DATE('now')
        ''', fetch='one')
        today_count = today_result['count'] if today_result else 0
        
        # Active (unused, non-expired) OTPs
        active_result = execute_query('''
            SELECT COUNT(*) as count FROM otp_codes 
            WHERE is_used = FALSE AND expires_at > ?
        ''', (datetime.now(),), fetch='one')
        active_count = active_result['count'] if active_result else 0
        
        return {
            'today_generated': today_count,
            'active_otps': active_count
        }

# Utility functions for easy integration
def send_login_otp(email, account_key="primary"):
    """Send OTP for login - utility function"""
    otp_auth = OTPAuthenticator()
    return otp_auth.create_otp(email, account_key)

def verify_login_otp(email, otp_code):
    """Verify OTP for login - utility function"""
    otp_auth = OTPAuthenticator()
    return otp_auth.verify_otp(email, otp_code)

def get_user_by_email(email):
    """Get user info after OTP verification - utility function"""
    otp_auth = OTPAuthenticator()
    return otp_auth.get_user_info(email)

def get_available_email_accounts_for_otp():
    """Get available email accounts for OTP sending"""
    return get_email_accounts()

if __name__ == "__main__":
    # Test the OTP system
    otp_auth = OTPAuthenticator()
    
    # Show available accounts
    accounts = get_available_email_accounts_for_otp()
    print("Available email accounts:")
    for i, account in enumerate(accounts):
        print(f"{i+1}. {account['name']} ({account['email']})")
    
    account_choice = input("Select account (1-2) or press Enter for default: ").strip()
    account_key = None
    if account_choice and account_choice.isdigit():
        idx = int(account_choice) - 1
        if 0 <= idx < len(accounts):
            account_key = accounts[idx]['key']
            print(f"Using account: {accounts[idx]['name']}")
    
    test_email = input("Enter email to test OTP: ").strip()
    if test_email:
        success, message = otp_auth.create_otp(test_email, account_key)
        print(f"OTP Creation: {message}")
        
        if success:
            otp_code = input("Enter the OTP you received: ").strip()
            success, message = otp_auth.verify_otp(test_email, otp_code)
            print(f"OTP Verification: {message}")
