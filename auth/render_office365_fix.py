# render_office365_fix.py - Enhanced Office 365 SMTP for Render deployment
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

class RenderOffice365Sender:
    """Enhanced Office 365 email sender with multiple SMTP fallbacks for Render"""
    
    def __init__(self):
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.display_name = os.getenv('EMAIL_DISPLAY_NAME', 'EduOps360 System')
        
        # Office 365 SMTP configurations optimized for Render
        self.office365_configs = [
            {
                'name': 'Office365 Primary',
                'server': 'smtp-mail.outlook.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'timeout': 60
            },
            {
                'name': 'Office365 Alternative',
                'server': 'smtp.office365.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'timeout': 60
            },
            {
                'name': 'Office365 SSL',
                'server': 'smtp-mail.outlook.com',
                'port': 465,
                'use_tls': False,
                'use_ssl': True,
                'timeout': 60
            },
            {
                'name': 'Office365 Alt SSL',
                'server': 'smtp.office365.com',
                'port': 465,
                'use_tls': False,
                'use_ssl': True,
                'timeout': 60
            },
            # Gmail fallback (if user has Gmail app password)
            {
                'name': 'Gmail Fallback',
                'server': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'timeout': 60
            }
        ]
    
    def test_smtp_connection(self, config):
        """Test SMTP connection with specific Office 365 configuration"""
        try:
            logger.info(f"🔍 Testing {config['name']} - {config['server']}:{config['port']}")
            print(f"🔍 Testing {config['name']} - {config['server']}:{config['port']}")
            
            if config['use_ssl']:
                # SSL connection (port 465)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    config['server'], 
                    config['port'], 
                    context=context, 
                    timeout=config['timeout']
                )
            else:
                # Regular connection (port 587)
                server = smtplib.SMTP(
                    config['server'], 
                    config['port'], 
                    timeout=config['timeout']
                )
                
                if config['use_tls']:
                    server.starttls()
            
            # Test login
            server.login(self.email_address, self.email_password)
            server.quit()
            
            logger.info(f"✅ {config['name']} connection successful")
            print(f"✅ {config['name']} connection successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ {config['name']} failed: {str(e)}")
            print(f"❌ {config['name']} failed: {str(e)}")
            return False
    
    def send_email_with_office365_fallback(self, to_email, subject, html_body, text_body=None):
        """Send email with Office 365 SMTP fallback"""
        
        if not self.email_address or not self.email_password:
            return {
                'success': False,
                'message': 'Office 365 credentials not configured. Please set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables.'
            }
        
        print(f"📧 Attempting to send email to {to_email}")
        print(f"📧 Using Office 365 account: {self.email_address}")
        
        # Try each Office 365 SMTP configuration
        for config in self.office365_configs:
            try:
                logger.info(f"📤 Attempting to send email via {config['name']}")
                print(f"📤 Attempting to send email via {config['name']}")
                
                # Create message
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{self.display_name} <{self.email_address}>"
                msg['To'] = to_email
                msg['Subject'] = subject
                msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
                
                # Add text part if provided
                if text_body:
                    text_part = MIMEText(text_body, 'plain', 'utf-8')
                    msg.attach(text_part)
                
                # Add HTML part
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
                
                # Send email
                if config['use_ssl']:
                    # SSL connection (port 465)
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(
                        config['server'], 
                        config['port'], 
                        context=context, 
                        timeout=config['timeout']
                    )
                else:
                    # Regular connection (port 587)
                    server = smtplib.SMTP(
                        config['server'], 
                        config['port'], 
                        timeout=config['timeout']
                    )
                    
                    if config['use_tls']:
                        server.starttls()
                
                # Enable debug output for troubleshooting
                server.set_debuglevel(1)
                
                # Login and send
                print(f"🔐 Logging in to {config['server']} with {self.email_address}")
                server.login(self.email_address, self.email_password)
                
                print(f"📤 Sending email...")
                server.send_message(msg)
                server.quit()
                
                logger.info(f"✅ Email sent successfully via {config['name']}")
                print(f"✅ Email sent successfully via {config['name']}")
                return {
                    'success': True,
                    'message': f'Email sent successfully via {config["name"]}',
                    'smtp_server': config['name']
                }
                
            except Exception as e:
                logger.error(f"❌ {config['name']} failed: {str(e)}")
                print(f"❌ {config['name']} failed: {str(e)}")
                continue
        
        # All Office 365 SMTP servers failed - show OTP in logs for Render
        error_msg = 'All Office 365 SMTP servers failed. Please check your credentials and network connectivity.'
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        
        # For Render deployment - show OTP in logs when email fails
        print("=" * 60)
        print("🚨 EMAIL DELIVERY FAILED - SHOWING OTP IN LOGS")
        print("=" * 60)
        print(f"📧 Email: {to_email}")
        print(f"🔑 OTP CODE: {otp_code if 'otp_code' in locals() else 'Not available'}")
        print(f"⏰ Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        
        return {
            'success': False,
            'message': error_msg,
            'show_otp_in_logs': True
        }
    
    def send_otp_email(self, to_email, otp_code):
        """Send OTP email with enhanced Office 365 reliability"""
        
        # Always show OTP in logs for Render debugging
        print("=" * 60)
        print("🔑 RENDER OTP DEBUG - EMAIL ATTEMPT")
        print("=" * 60)
        print(f"📧 Email: {to_email}")
        print(f"🔑 OTP CODE: {otp_code}")
        print(f"⏰ Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        
        subject = "Your EduOps360 Login OTP"
        
        # Create both HTML and text versions
        text_body = f"""
Your EduOps360 Login OTP

Hello,

Your One-Time Password (OTP) for EduOps360 login is: {otp_code}

This OTP is valid for 10 minutes. Please do not share this code with anyone.

If you did not request this OTP, please ignore this email.

Best regards,
EduOps360 Team
        """
        
        html_body = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>EduOps360 OTP</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            
            <h2 style="color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 10px;">EduOps360 Login OTP</h2>
            
            <p>Hello,</p>
            
            <p>Your One-Time Password (OTP) for EduOps360 login is:</p>
            
            <div style="background-color: #f8f9fa; border: 2px solid #2c5aa0; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <h1 style="color: #2c5aa0; font-size: 32px; margin: 0; letter-spacing: 8px;">{otp_code}</h1>
            </div>
            
            <p><strong>Important:</strong></p>
            <ul>
                <li>This OTP is valid for <strong>10 minutes</strong></li>
                <li>Please do not share this code with anyone</li>
                <li>If you did not request this OTP, please ignore this email</li>
            </ul>
            
            <p><strong>Best regards,</strong><br>
            <strong>EduOps360 Team</strong></p>
            
        </body>
        </html>
        """
        
        result = self.send_email_with_office365_fallback(to_email, subject, html_body, text_body)
        
        # Show result in logs
        if result.get('success'):
            print(f"✅ EMAIL SENT SUCCESSFULLY via {result.get('smtp_server', 'Unknown')}")
        else:
            print("❌ EMAIL FAILED - OTP SHOWN ABOVE IN LOGS")
            print(f"❌ Error: {result.get('message', 'Unknown error')}")
        
        return result

# Global instance for easy import
render_office365_sender = RenderOffice365Sender()

def send_otp_email_render(to_email, otp_code):
    """Convenience function to send OTP email via Render-optimized Office 365"""
    return render_office365_sender.send_otp_email(to_email, otp_code)

def test_office365_connection():
    """Test all Office 365 SMTP configurations"""
    print("🔍 Testing Office 365 SMTP configurations for Render...")
    
    for config in render_office365_sender.office365_configs:
        render_office365_sender.test_smtp_connection(config)
    
    print("✅ SMTP connection test completed")
