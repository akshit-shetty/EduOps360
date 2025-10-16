#!/usr/bin/env python3
"""
Test Microsoft email configuration for Session Reminder
"""
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def test_microsoft_smtp():
    """Test Microsoft SMTP connection"""
    
    print("🔍 TESTING MICROSOFT EMAIL CONFIGURATION")
    print("=" * 45)
    
    # Get email credentials from .env
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')
    
    if not email_address or not email_password:
        print("❌ EMAIL_ADDRESS or EMAIL_PASSWORD not found in .env file")
        print("\n💡 Add these to your .env file:")
        print("EMAIL_ADDRESS=your-email@upgrad.com")
        print("EMAIL_PASSWORD=your-app-password")
        return
    
    print(f"📧 Testing email: {email_address}")
    print(f"🔑 Password length: {len(email_password)} characters")
    
    # Test Microsoft SMTP servers
    microsoft_servers = [
        ("Microsoft TLS", "smtp-mail.outlook.com", 587, True),
        ("Microsoft SSL", "smtp-mail.outlook.com", 465, False),
    ]
    
    for name, server, port, use_tls in microsoft_servers:
        print(f"\n📧 Testing {name} ({server}:{port})")
        print("-" * 35)
        
        # Test socket connection
        try:
            print(f"🔍 Testing socket connection...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8)
            result = sock.connect_ex((server, port))
            sock.close()
            
            if result == 0:
                print(f"✅ Socket connection successful")
            else:
                print(f"❌ Socket connection failed (code: {result})")
                continue
                
        except Exception as e:
            print(f"❌ Socket test failed: {e}")
            continue
        
        # Test SMTP connection and authentication
        try:
            print(f"🔍 Testing SMTP connection and authentication...")
            
            if use_tls:
                # TLS connection (port 587)
                server_obj = smtplib.SMTP(server, port, timeout=15)
                print(f"🔍 Starting TLS...")
                server_obj.starttls()
            else:
                # SSL connection (port 465)
                server_obj = smtplib.SMTP_SSL(server, port, timeout=15)
            
            print(f"✅ SMTP connection established")
            
            # Test authentication
            print(f"🔍 Testing authentication...")
            server_obj.login(email_address, email_password)
            print(f"✅ Authentication successful!")
            
            # Test sending email to yourself
            print(f"🔍 Testing email send...")
            msg = MIMEMultipart()
            msg['From'] = email_address
            msg['To'] = email_address  # Send to yourself
            msg['Subject'] = "EduOps360 Microsoft Email Test"
            
            body = f"""
🎉 SUCCESS! Microsoft Email Configuration Test

✅ SMTP Server: {server}:{port}
✅ Authentication: Working
✅ Email Account: {email_address}
✅ Connection Type: {'TLS' if use_tls else 'SSL'}

This test email confirms that your Microsoft email configuration is working correctly for the EduOps360 Session Reminder tool.

📧 Sent from EduOps360 Session Reminder Test
🕒 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server_obj.send_message(msg)
            print(f"✅ Test email sent successfully to {email_address}!")
            print(f"📧 Check your inbox for the test email")
            
            server_obj.quit()
            
            print(f"\n🎉 MICROSOFT EMAIL CONFIGURATION WORKING!")
            print(f"✅ Server: {server}:{port}")
            print(f"✅ Account: {email_address}")
            print(f"✅ Authentication: Success")
            print(f"✅ Email Send: Success")
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            print(f"💡 Check your App Password:")
            print(f"   1. Go to Microsoft Account Security settings")
            print(f"   2. Enable 2-Factor Authentication")
            print(f"   3. Generate App Password for 'Mail'")
            print(f"   4. Use App Password (not regular password)")
            
        except Exception as e:
            print(f"❌ SMTP connection/send failed: {e}")
        
        try:
            server_obj.quit()
        except:
            pass
    
    print(f"\n❌ All Microsoft SMTP tests failed")
    return False

def show_env_template():
    """Show .env file template for Microsoft email"""
    
    print(f"\n📝 .ENV FILE TEMPLATE FOR MICROSOFT EMAIL:")
    print("=" * 45)
    
    template = """
# Microsoft Email Configuration for EduOps360
EMAIL_ADDRESS=your-email@upgrad.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_DISPLAY_NAME=Your Name

# Optional: Force specific SMTP settings
EMAIL_SMTP_SERVER=smtp-mail.outlook.com
EMAIL_SMTP_PORT=587
EMAIL_USE_TLS=true
"""
    
    print(template)
    
    print(f"\n💡 MICROSOFT APP PASSWORD SETUP:")
    print("-" * 30)
    print("1. Go to https://account.microsoft.com/security")
    print("2. Sign in with your Microsoft account")
    print("3. Go to 'Security' → 'Advanced security options'")
    print("4. Enable 'Two-step verification' if not already enabled")
    print("5. Go to 'App passwords' → 'Create a new app password'")
    print("6. Choose 'Mail' as the app type")
    print("7. Copy the generated password to EMAIL_PASSWORD in .env")
    print("8. Save .env file and restart the application")

if __name__ == "__main__":
    success = test_microsoft_smtp()
    
    if not success:
        show_env_template()
    else:
        print(f"\n🚀 Your Microsoft email is ready for Session Reminder!")
        print(f"✅ The Session Reminder tool should now work correctly")
