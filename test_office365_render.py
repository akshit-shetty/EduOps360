#!/usr/bin/env python3
"""
Test Office 365 SMTP configuration for Render deployment
Run this script to test your Office 365 email setup
"""

import os
from dotenv import load_dotenv
from auth.render_office365_fix import test_office365_connection, send_otp_email_render

# Load environment variables
load_dotenv()

def main():
    print("🔍 Testing Office 365 SMTP Configuration for Render")
    print("=" * 50)
    
    # Check environment variables
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')
    email_display_name = os.getenv('EMAIL_DISPLAY_NAME', 'EduOps360 System')
    
    print(f"📧 Email Address: {email_address}")
    print(f"🏷️  Display Name: {email_display_name}")
    print(f"🔐 Password: {'✅ Configured' if email_password else '❌ Not configured'}")
    print()
    
    if not email_address or not email_password:
        print("❌ ERROR: EMAIL_ADDRESS and EMAIL_PASSWORD must be set in environment variables")
        print("Please configure your Office 365 credentials in .env file:")
        print("EMAIL_ADDRESS=your-office365-email@domain.com")
        print("EMAIL_PASSWORD=your-app-password")
        print("EMAIL_DISPLAY_NAME=EduOps360 System")
        return
    
    # Test SMTP connections
    print("🔍 Testing SMTP Connections...")
    print("-" * 30)
    test_office365_connection()
    print()
    
    # Test sending OTP email
    test_email = input(f"Enter test email address (or press Enter to use {email_address}): ").strip()
    if not test_email:
        test_email = email_address
    
    print(f"📤 Testing OTP email send to: {test_email}")
    print("-" * 30)
    
    test_otp = "123456"
    result = send_otp_email_render(test_email, test_otp)
    
    print()
    print("📊 Test Results:")
    print("-" * 15)
    if result.get('success'):
        print(f"✅ SUCCESS: {result.get('message')}")
        print(f"📡 SMTP Server: {result.get('smtp_server')}")
    else:
        print(f"❌ FAILED: {result.get('message')}")
    
    print()
    print("🎯 Recommendations for Render:")
    print("-" * 30)
    print("1. Ensure your Office 365 account has 'Less secure app access' enabled")
    print("2. Use App Passwords instead of regular passwords")
    print("3. Check that your Office 365 account is not blocked by Microsoft")
    print("4. Verify that Render allows outbound SMTP connections")
    print("5. Consider using Gmail as a fallback if Office 365 fails")

if __name__ == "__main__":
    main()
