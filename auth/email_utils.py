# email_utils.py - Cross-platform SMTP email utilities with multi-account support
import os
from datetime import datetime
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from .email_config import EmailAccount, get_account_by_key, get_default_account

load_dotenv()
logger = logging.getLogger(__name__)

class SMTPEmailSender:
    """Cross-platform SMTP email sender with multi-account support"""
    
    def __init__(self, account_key: str = None, account: EmailAccount = None):
        load_dotenv()
        
        print(f"🔍 SMTPEmailSender init with account_key: {account_key}")
        
        # Use provided account or get default
        if account:
            self.account = account
            print(f"🔍 Using provided account: {account.name}")
        elif account_key:
            self.account = get_account_by_key(account_key)
            if not self.account:
                print(f"❌ Email account '{account_key}' not found")
                raise ValueError(f"Email account '{account_key}' not found")
            print(f"🔍 Found account by key: {self.account.name} ({self.account.email})")
        else:
            self.account = get_default_account()
            if not self.account:
                print(f"❌ No email accounts configured")
                raise ValueError("No email accounts configured")
            print(f"🔍 Using default account: {self.account.name}")
        
        # Set SMTP configuration from account
        self.smtp_server = self.account.smtp_server
        self.smtp_port = self.account.smtp_port
        self.smtp_username = self.account.email
        self.smtp_password = self.account.password
        self.use_tls = self.account.use_tls
        self.sender_name = self.account.name
        
        print(f"🔍 SMTP Config - Server: {self.smtp_server}:{self.smtp_port}, User: {self.smtp_username}")
        
        # Auto-detect email provider settings if needed (but account config takes priority)
        if self.smtp_username and not hasattr(self, 'account'):
            self._auto_configure_provider()
        
        if not self.smtp_password:
            print(f"❌ SMTP credentials not configured for account: {self.account.name}")
            logger.warning(f"SMTP credentials not configured for account: {self.account.name}")
        else:
            print(f"🔍 SMTP password configured: {'*' * len(self.smtp_password)}")
    
    def _auto_configure_provider(self):
        """Auto-configure Office365 SMTP settings for all providers"""
        # All emails use Office365 SMTP configuration
        self.smtp_server = 'smtp-mail.outlook.com'
        self.smtp_port = 587
        self.use_tls = True
        logger.info("Using Office365 SMTP configuration for all email providers")
        
    def send_email(self, to_email, subject, body, attachments=None, is_html=True):
        """
        Send email using SMTP
{{ ... }}
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body (str): Email body content
            attachments (list): List of file paths to attach
            is_html (bool): Whether body is HTML or plain text
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            # Create message with anti-spam headers
            msg = MIMEMultipart('alternative')
            
            # Use custom from_email if provided via sender_name override
            if hasattr(self, 'custom_from_email') and self.custom_from_email:
                msg['From'] = f"{self.sender_name} <{self.custom_from_email}>"
            else:
                msg['From'] = f"{self.sender_name} <{self.smtp_username}>"
            
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Keep headers minimal to avoid spam filters
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if any
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as attachment:
                            part = MIMEApplication(attachment.read())
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            msg.attach(part)
                    else:
                        logger.warning(f"Attachment file not found: {file_path}")
            
            # Try multiple SMTP configurations with fallbacks
            smtp_configs = [
                # Primary Office365 configuration
                {
                    'server': self.smtp_server,
                    'port': self.smtp_port,
                    'use_ssl': self.smtp_port == 465,
                    'name': 'Office365 Primary'
                },
                # Alternative Office365 ports
                {
                    'server': 'smtp-mail.outlook.com',
                    'port': 25,
                    'use_ssl': False,
                    'name': 'Office365 Port 25'
                },
                {
                    'server': 'smtp.office365.com',
                    'port': 587,
                    'use_ssl': False,
                    'name': 'Office365 Alternative'
                },
                # Gmail as fallback (if configured)
                {
                    'server': 'smtp.gmail.com',
                    'port': 587,
                    'use_ssl': False,
                    'name': 'Gmail Fallback'
                }
            ]
            
            last_error = None
            
            for config in smtp_configs:
                try:
                    print(f"🔍 Trying {config['name']}: {config['server']}:{config['port']}")
                    
                    # Test connection first
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)  # Shorter timeout for faster fallback
                    result = sock.connect_ex((config['server'], config['port']))
                    sock.close()
                    
                    if result != 0:
                        print(f"❌ Connection test failed for {config['name']}")
                        continue
                    
                    print(f"✅ Connection test passed for {config['name']}")
                    
                    # Attempt SMTP connection
                    if config['use_ssl']:
                        server = smtplib.SMTP_SSL(config['server'], config['port'], timeout=10)
                    else:
                        server = smtplib.SMTP(config['server'], config['port'], timeout=10)
                        if config['port'] in [587, 25]:  # Enable TLS for these ports
                            server.starttls()
                    
                    # Login and send
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                    server.quit()
                    
                    print(f"✅ Email sent successfully via {config['name']}")
                    return {
                        'success': True,
                        'message': f'Email sent successfully via {config["name"]}',
                        'provider': config['name']
                    }
                    
                except Exception as e:
                    print(f"❌ Failed with {config['name']}: {e}")
                    last_error = e
                    try:
                        if 'server' in locals():
                            server.quit()
                    except:
                        pass
                    continue
            
            # If all SMTP methods failed, return fallback message
            print(f"❌ All SMTP methods failed. Last error: {last_error}")
            
            # Check if we're in a cloud environment that blocks SMTP
            cloud_indicators = [
                os.getenv('RENDER_SERVICE_ID'),
                os.getenv('HEROKU_APP_NAME'),
                os.getenv('VERCEL_ENV'),
                os.getenv('NETLIFY_BUILD_BASE'),
                os.getenv('RAILWAY_ENVIRONMENT'),  # Railway detection
                os.getenv('RAILWAY_PROJECT_ID'),   # Railway detection
                os.path.exists('/opt/render'),
                os.path.exists('/app')  # Common in containerized environments
            ]
            
            if any(cloud_indicators):
                print("🌐 Cloud environment detected - SMTP may be blocked")
                return {
                    'success': False,
                    'message': f'SMTP blocked in cloud environment. Email content: {body[:100]}...',
                    'fallback_content': body,
                    'cloud_environment': True
                }
            
            # Return the last error
            raise Exception(f"All SMTP servers failed. Last error: {last_error}")
            
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            print(f"❌ SMTP Error: {error_msg}")
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': error_msg}
    
    def send_bulk_emails(self, email_list, subject_template, body_template, preview_only=False):
        """
        Send bulk emails with personalization
        
        Args:
            email_list (list): List of dicts with email data
            subject_template (str): Subject template with placeholders
            body_template (str): Body template with placeholders
            preview_only (bool): If True, only generate previews without sending
            
        Returns:
            dict: Results summary
        """
        results = {
            'sent': 0,
            'failed': 0,
            'previews': [],
            'errors': []
        }
        
        for email_data in email_list:
            try:
                # Replace placeholders in subject and body
                subject = subject_template.format(**email_data)
                body = body_template.format(**email_data)
                
                if preview_only:
                    results['previews'].append({
                        'to': email_data.get('email', ''),
                        'subject': subject,
                        'body': body
                    })
                else:
                    # Send actual email
                    result = self.send_email(
                        to_email=email_data.get('email', ''),
                        subject=subject,
                        body=body,
                        is_html=True
                    )
                    
                    if result['success']:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(result['message'])
                        
            except Exception as e:
                results['errors'].append(f"Error processing {email_data.get('email', 'unknown')}: {str(e)}")
        
        return results

# Main function for sending emails via SMTP with account selection
def send_smtp_email(to_email, subject, html_body, text_body=None, attachments=None, from_email=None, from_name=None, account_key=None):
    """Send email using SMTP configuration with account selection
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_body (str): Email body content (HTML format)
        text_body (str): Email body content (plain text format)
        attachments (list): List of file paths to attach
        from_email (str): Custom sender email (optional)
        from_name (str): Custom sender name (optional)
        account_key (str): Email account key to use (optional, uses default if not provided)
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        sender = SMTPEmailSender(account_key=account_key)
        
        # Use custom from_name if provided
        if from_name:
            sender.sender_name = from_name
        
        # Use custom from_email if provided (for display only, authentication still uses smtp_username)
        if from_email:
            sender.custom_from_email = from_email
        
        return sender.send_email(to_email, subject, html_body, attachments, is_html=True)
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return {'success': False, 'message': str(e)}

# Global instance for easy use (uses default account)
# Initialize lazily to avoid issues with environment variables
email_sender = None

def get_default_email_sender():
    """Get or create default email sender instance"""
    global email_sender
    if email_sender is None:
        try:
            email_sender = SMTPEmailSender()
        except Exception as e:
            logger.warning(f"Failed to initialize default email sender: {e}")
            return None
    return email_sender

# Backward compatibility function names
def send_outlook_email(to_email, subject, body, attachments=None, account_key=None):
    """Backward compatibility - now uses SMTP with account selection"""
    return send_smtp_email(to_email, subject, body, attachments=attachments, account_key=account_key)

# New convenience functions for multi-account support
def send_email_with_account(to_email, subject, html_body, account_key, attachments=None):
    """Send email using specific account"""
    return send_smtp_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        account_key=account_key
    )

def get_available_email_accounts():
    """Get list of available email accounts for UI"""
    from .email_config import get_email_accounts
    return get_email_accounts()
