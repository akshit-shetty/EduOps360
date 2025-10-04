# email_utils.py - Cross-platform SMTP email utilities
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class SMTPEmailSender:
    """Cross-platform SMTP email sender"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.username = os.getenv('SMTP_USERNAME', '')
        self.password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.username)
        
        if not self.username or not self.password:
            logger.warning("SMTP credentials not configured. Email functionality will not work.")
        
    def send_email(self, to_email, subject, body, attachments=None, is_html=True):
        """
        Send email using SMTP
        
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
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
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
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable encryption
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return {'success': True, 'message': 'Email sent successfully via SMTP'}
            
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
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
                results['failed'] += 1
                results['errors'].append(f"Error processing {email_data.get('email', 'unknown')}: {str(e)}")
        
        return results

# Main function for sending emails via SMTP
def send_smtp_email(to_email, subject, body, attachments=None):
    """
    Send email using SMTP (cross-platform)
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content (HTML format)
        attachments (list): List of file paths to attach
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    sender = SMTPEmailSender()
    return sender.send_email(to_email, subject, body, attachments, is_html=True)

# Global instance for easy use
email_sender = SMTPEmailSender()

# Backward compatibility function names
def send_outlook_email(to_email, subject, body, attachments=None):
    """Backward compatibility - now uses SMTP"""
    return send_smtp_email(to_email, subject, body, attachments)
