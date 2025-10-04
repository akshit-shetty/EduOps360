# email_utils.py - Windows Outlook email utilities
import os
import logging

logger = logging.getLogger(__name__)

class OutlookEmailSender:
    """Windows Outlook email sender using win32com"""
    
    def __init__(self):
        try:
            import win32com.client
            self.outlook = win32com.client.Dispatch("Outlook.Application")
        except ImportError:
            raise ImportError("win32com.client is required for Outlook integration. Install with: pip install pywin32")
        except Exception as e:
            raise Exception(f"Failed to initialize Outlook: {str(e)}")
        
    def send_email(self, to_email, subject, body, attachments=None, is_html=True):
        """
        Send email using Outlook
        
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
            mail = self.outlook.CreateItem(0)  # 0 is the mail item
            
            mail.To = to_email
            mail.Subject = subject
            
            # Set body based on format
            if is_html:
                mail.HTMLBody = body
            else:
                mail.Body = body
            
            # Add attachments if any
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        mail.Attachments.Add(file_path)
                    else:
                        logger.warning(f"Attachment file not found: {file_path}")
            
            mail.Send()
            logger.info(f"Email sent successfully to {to_email}")
            return {'success': True, 'message': 'Email sent successfully via Outlook'}
            
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

# Main function for sending emails via Outlook
def send_outlook_email(to_email, subject, body, attachments=None):
    """
    Send email using Outlook (Windows only)
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content (HTML format)
        attachments (list): List of file paths to attach
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        import win32com.client
        
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 is the mail item
        
        mail.To = to_email
        mail.Subject = subject
        mail.HTMLBody = body
        
        # Add attachments if any
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    mail.Attachments.Add(file_path)
                else:
                    logger.warning(f"Attachment file not found: {file_path}")
        
        mail.Send()
        logger.info(f"Email sent successfully to {to_email}")
        return {'success': True, 'message': 'Email sent via Outlook'}
        
    except ImportError:
        error_msg = "win32com.client is required for Outlook integration. Install with: pip install pywin32"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
        
    except Exception as e:
        error_msg = f"Failed to send email via Outlook: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}

# Global instance for easy use
email_sender = OutlookEmailSender()
