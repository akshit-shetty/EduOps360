# email_campaigns.py - Email Campaign Management System
from flask import Flask, jsonify, request, render_template, Blueprint
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import threading
from functools import wraps
import tempfile
import uuid
import sqlite3
import re
from auth.email_utils import send_smtp_email
from auth.email_config import get_email_accounts, get_account_by_key

campaigns_bp = Blueprint("campaigns", __name__)
CORS(campaigns_bp)

# Email validation function
def validate_email_format(email):
    """
    Validate email format and check for common issues
    Returns True if email is valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic format check - must have @ and domain
    if '@' not in email:
        return False
    
    # Split into local and domain parts
    parts = email.split('@')
    if len(parts) != 2:
        return False
    
    local_part, domain = parts
    
    # Check local part (before @)
    if not local_part or len(local_part) > 64:
        return False
    
    # Check domain part (after @)
    if not domain or len(domain) > 255:
        return False
    
    # Domain must have at least one dot
    if '.' not in domain:
        return False
    
    # Check for invalid characters
    if '..' in email or email.startswith('.') or email.endswith('.'):
        return False
    
    # Basic regex pattern for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False
    
    # Check for invalid domains
    invalid_domains = ['localhost', '127.0.0.1', 'example.com', 'test.test', 'invalid']
    domain_lower = domain.lower()
    
    if domain_lower in invalid_domains:
        return False
    
    # Check for suspicious TLDs or patterns
    suspicious_patterns = [
        r'\.cc$',  # .cc domains are often suspicious
        r'\.tk$',  # .tk domains are often temporary
        r'\.ml$',  # .ml domains are often temporary
        r'\.ga$',  # .ga domains are often temporary
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, domain_lower):
            return False
    
    return True

def get_current_user_info():
    """Get current user information from session and database"""
    from flask import session
    
    # Try to get user ID from session
    user_id = session.get('user_id') or session.get('id') or session.get('current_user_id')
    
    if not user_id:
        return {'id': None, 'name': 'Admin User', 'full_name': 'Admin User'}
    
    try:
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        
        # Get user information from database
        cursor.execute('''
            SELECT id, first_name, last_name, email
            FROM users 
            WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            first_name = user[1] or ''
            last_name = user[2] or ''
            full_name = f"{first_name} {last_name}".strip()
            
            return {
                'id': user[0],
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name if full_name else 'Admin User',
                'email': user[3]
            }
        else:
            return {'id': user_id, 'name': 'Admin User', 'full_name': 'Admin User'}
            
    except Exception as e:
        print(f"Error getting user info: {e}")
        return {'id': user_id, 'name': 'Admin User', 'full_name': 'Admin User'}

def get_user_name_by_id(user_id):
    """Get user's full name by user ID"""
    if not user_id:
        return 'Admin User'
    
    try:
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT first_name, last_name
            FROM users 
            WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            first_name = user[0] or ''
            last_name = user[1] or ''
            full_name = f"{first_name} {last_name}".strip()
            return full_name if full_name else 'Admin User'
        else:
            return 'Admin User'
            
    except Exception as e:
        print(f"Error getting user name: {e}")
        return 'Admin User'

# Global state for campaign management
campaigns_data = {}
campaign_status = {}
email_templates = {}

def run_in_thread(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return decorated_function

# ==============================
# Database Setup for Campaigns
# ==============================
def init_campaigns_db():
    """Initialize campaigns database tables"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    # Email Campaigns table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            template_id TEXT,
            template_content TEXT,
            recipient_list TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scheduled_at TIMESTAMP,
            sent_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_recipients INTEGER DEFAULT 0,
            emails_sent INTEGER DEFAULT 0,
            emails_failed INTEGER DEFAULT 0,
            emails_pending INTEGER DEFAULT 0,
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0,
            bounce_rate REAL DEFAULT 0.0,
            created_by TEXT,
            email_account TEXT,
            campaign_type TEXT DEFAULT 'bulk',
            priority TEXT DEFAULT 'normal',
            tags TEXT,
            notes TEXT
        )
    ''')
    
    # Email Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            html_content TEXT NOT NULL,
            text_content TEXT,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Campaign Recipients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_recipients (
            id TEXT PRIMARY KEY,
            campaign_id TEXT,
            email TEXT NOT NULL,
            name TEXT,
            first_name TEXT,
            last_name TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            delivered_at TIMESTAMP,
            opened_at TIMESTAMP,
            clicked_at TIMESTAMP,
            bounced_at TIMESTAMP,
            unsubscribed_at TIMESTAMP,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TIMESTAMP,
            custom_fields TEXT,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id)
        )
    ''')
    
    # Campaign Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_analytics (
            id TEXT PRIMARY KEY,
            campaign_id TEXT,
            event_type TEXT,
            recipient_email TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            location TEXT,
            device_type TEXT,
            metadata TEXT,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id)
        )
    ''')
    
    # Campaign Attachments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_attachments (
            id TEXT PRIMARY KEY,
            campaign_id TEXT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id)
        )
    ''')
    
    # Campaign Links table (for click tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_links (
            id TEXT PRIMARY KEY,
            campaign_id TEXT,
            original_url TEXT NOT NULL,
            tracking_url TEXT NOT NULL,
            link_text TEXT,
            click_count INTEGER DEFAULT 0,
            unique_clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id)
        )
    ''')
    
    # Campaign Schedules table (for scheduled campaigns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_schedules (
            id TEXT PRIMARY KEY,
            campaign_id TEXT,
            scheduled_time TIMESTAMP NOT NULL,
            timezone TEXT DEFAULT 'UTC',
            repeat_type TEXT,
            repeat_interval INTEGER,
            end_date TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id)
        )
    ''')
    
    conn.commit()
    
    # Add missing columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN template_content TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN completed_at TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN emails_pending INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN bounce_rate REAL DEFAULT 0.0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN campaign_type TEXT DEFAULT 'bulk'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN priority TEXT DEFAULT 'normal'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN tags TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE email_campaigns ADD COLUMN notes TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add missing columns to campaign_recipients table
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN first_name TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN last_name TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN delivered_at TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN unsubscribed_at TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN retry_count INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN last_retry_at TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_recipients ADD COLUMN custom_fields TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add missing columns to campaign_analytics table
    try:
        cursor.execute("ALTER TABLE campaign_analytics ADD COLUMN ip_address TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_analytics ADD COLUMN user_agent TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_analytics ADD COLUMN location TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE campaign_analytics ADD COLUMN device_type TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.close()

# Initialize database on import
init_campaigns_db()

# ==============================
# Text to HTML Conversion
# ==============================
def convert_text_to_html(text_content):
    """Convert plain text email content to professional HTML"""
    if not text_content:
        return ""
    
    # Escape HTML characters
    import html
    text_content = html.escape(text_content)
    
    # Convert line breaks to HTML
    text_content = text_content.replace('\r\n', '\n')  # Normalize line endings
    
    # Split into paragraphs (double line breaks)
    paragraphs = text_content.split('\n\n')
    
    html_content = []
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        # Check if it's a list (starts with bullet point)
        if '•' in paragraph or paragraph.startswith('- '):
            # Convert to HTML list
            lines = paragraph.split('\n')
            list_items = []
            for line in lines:
                line = line.strip()
                if line.startswith('•') or line.startswith('-'):
                    # Remove bullet and add as list item
                    item = line[1:].strip()
                    if item:
                        list_items.append(f'<li>{item}</li>')
                elif line and not (line.startswith('•') or line.startswith('-')):
                    # Non-list line, add as paragraph before list
                    if list_items:
                        html_content.append(f'<p>{line}</p>')
                    else:
                        html_content.append(f'<p>{line}</p>')
            
            if list_items:
                html_content.append('<ul>' + ''.join(list_items) + '</ul>')
        
        elif paragraph.startswith('---'):
            # Horizontal rule
            html_content.append('<hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">')
        
        else:
            # Regular paragraph - handle single line breaks within paragraph
            paragraph = paragraph.replace('\n', '<br>')
            html_content.append(f'<p>{paragraph}</p>')
    
    # Join all HTML content
    body_html = ''.join(html_content)
    
    # Create complete HTML email template - Clean and professional without branding
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333333;
            margin: 0;
            padding: 20px;
            background-color: #f9fafb;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content p {{
            margin-bottom: 16px;
            color: #374151;
            font-size: 16px;
        }}
        .content ul {{
            margin: 16px 0;
            padding-left: 20px;
        }}
        .content li {{
            margin-bottom: 8px;
            color: #374151;
            font-size: 16px;
        }}
        .content h1, .content h2, .content h3 {{
            color: #1f2937;
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        .footer {{
            background: #f9fafb;
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 24px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            {body_html}
        </div>
        <div class="footer">
            <p>This is an automated email. Please do not reply to this message.</p>
        </div>
    </div>
</body>
</html>"""
    
    return html_template

# ==============================
# Campaign Management Functions
# ==============================

def create_campaign(name, subject, template_id, recipient_list, email_account, created_by, scheduled_at=None, campaign_type='bulk', priority='normal', tags=None, notes=None):
    """Create a new email campaign"""
    campaign_id = str(uuid.uuid4())
    
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    # Get template content for storage
    template_content = None
    if template_id:
        template = get_template(template_id)
        if template:
            template_content = template['html_content']
            # If template content doesn't look like HTML, convert it
            if template_content and not template_content.strip().startswith('<!DOCTYPE'):
                template_content = convert_text_to_html(template_content)
    
    cursor.execute('''
        INSERT INTO email_campaigns 
        (id, name, subject, template_id, template_content, recipient_list, email_account, created_by, 
         scheduled_at, total_recipients, emails_pending, campaign_type, priority, tags, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (campaign_id, name, subject, template_id, template_content, json.dumps(recipient_list), 
          email_account, created_by, scheduled_at, len(recipient_list), len(recipient_list),
          campaign_type, priority, json.dumps(tags) if tags else None, notes))
    
    # Add recipients with detailed information
    for recipient in recipient_list:
        recipient_id = str(uuid.uuid4())
        
        # Parse name into first_name and last_name if possible
        full_name = recipient.get('name', '')
        name_parts = full_name.split(' ', 1) if full_name else ['', '']
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        cursor.execute('''
            INSERT INTO campaign_recipients 
            (id, campaign_id, email, name, first_name, last_name, custom_fields)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (recipient_id, campaign_id, recipient['email'], full_name, first_name, last_name,
              json.dumps(recipient.get('custom_fields', {}))))
    
    # Log campaign creation event
    cursor.execute('''
        INSERT INTO campaign_analytics (id, campaign_id, event_type, metadata)
        VALUES (?, ?, 'campaign_created', ?)
    ''', (str(uuid.uuid4()), campaign_id, json.dumps({
        'total_recipients': len(recipient_list),
        'created_by': created_by,
        'email_account': email_account
    })))
    
    conn.commit()
    conn.close()
    
    return campaign_id

def get_campaign(campaign_id):
    """Get campaign details"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM email_campaigns WHERE id = ?', (campaign_id,))
    campaign = cursor.fetchone()
    
    if campaign:
        # Get column names
        columns = [description[0] for description in cursor.description]
        campaign_dict = dict(zip(columns, campaign))
        
        # Resolve created_by user ID to user name
        campaign_dict['created_by'] = get_user_name_by_id(campaign_dict['created_by'])
        
        # Get recipients
        cursor.execute('SELECT * FROM campaign_recipients WHERE campaign_id = ?', (campaign_id,))
        recipients = cursor.fetchall()
        recipient_columns = [description[0] for description in cursor.description]
        campaign_dict['recipients'] = [dict(zip(recipient_columns, recipient)) for recipient in recipients]
        
        conn.close()
        return campaign_dict
    
    conn.close()
    return None

def get_all_campaigns():
    """Get all campaigns"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, subject, status, created_at, scheduled_at, sent_at,
               total_recipients, emails_sent, emails_failed, open_rate, click_rate,
               created_by, email_account
        FROM email_campaigns 
        ORDER BY created_at DESC
    ''')
    
    campaigns = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    conn.close()
    
    # Convert to dict and resolve user names
    campaign_list = []
    for campaign in campaigns:
        campaign_dict = dict(zip(columns, campaign))
        # Resolve created_by user ID to user name
        campaign_dict['created_by'] = get_user_name_by_id(campaign_dict['created_by'])
        campaign_list.append(campaign_dict)
    
    return campaign_list

def clear_all_campaigns_and_templates():
    """Clear all campaigns and templates from database"""
    try:
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        
        # Delete all campaign-related data
        cursor.execute('DELETE FROM campaign_analytics')
        cursor.execute('DELETE FROM campaign_recipients') 
        cursor.execute('DELETE FROM campaign_attachments')
        cursor.execute('DELETE FROM campaign_links')
        cursor.execute('DELETE FROM campaign_schedules')
        cursor.execute('DELETE FROM email_campaigns')
        
        # Delete all templates
        cursor.execute('DELETE FROM email_templates')
        
        conn.commit()
        conn.close()
        
        print("✅ All campaigns and templates deleted successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

@run_in_thread
def send_campaign(campaign_id):
    """Send email campaign"""
    global campaign_status
    
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            return
        
        # Update campaign status to sending
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE email_campaigns 
            SET status = 'sending', sent_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (campaign_id,))
        conn.commit()
        
        # Get template
        template = get_template(campaign['template_id'])
        if not template:
            cursor.execute('''
                UPDATE email_campaigns SET status = 'failed' WHERE id = ?
            ''', (campaign_id,))
            conn.commit()
            conn.close()
            return
        
        # Ensure template content is HTML
        template_html = template['html_content']
        if template_html and not template_html.strip().startswith('<!DOCTYPE'):
            template_html = convert_text_to_html(template_html)
        
        sent_count = 0
        failed_count = 0
        
        # Send to each recipient
        for recipient in campaign['recipients']:
            try:
                # Personalize email content
                html_content = template_html.replace('{{name}}', recipient['name'] or 'Valued Learner')
                html_content = html_content.replace('{{email}}', recipient['email'])
                html_content = html_content.replace('{{first_name}}', recipient['first_name'] or 'Valued')
                html_content = html_content.replace('{{last_name}}', recipient['last_name'] or 'Learner')
                
                # Validate email format first
                if not validate_email_format(recipient['email']):
                    failed_count += 1
                    cursor.execute('''
                        UPDATE campaign_recipients 
                        SET status = 'failed', error_message = 'Invalid email format'
                        WHERE campaign_id = ? AND email = ?
                    ''', (campaign_id, recipient['email']))
                    continue
                
                # Send email
                result = send_smtp_email(
                    to_email=recipient['email'],
                    subject=campaign['subject'],
                    html_body=html_content,
                    account_key=campaign['email_account']
                )
                
                if result['success']:
                    sent_count += 1
                    # Update recipient status
                    cursor.execute('''
                        UPDATE campaign_recipients 
                        SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                        WHERE campaign_id = ? AND email = ?
                    ''', (campaign_id, recipient['email']))
                else:
                    failed_count += 1
                    # Update recipient status with error
                    cursor.execute('''
                        UPDATE campaign_recipients 
                        SET status = 'failed', error_message = ?
                        WHERE campaign_id = ? AND email = ?
                    ''', (result.get('error', 'Unknown error'), campaign_id, recipient['email']))
                    
            except Exception as e:
                cursor.execute('''
                    UPDATE campaign_recipients 
                    SET status = 'failed', error_message = ? 
                    WHERE id = ?
                ''', (str(e), recipient['id']))
                failed_count += 1
        
        # Update campaign final status with comprehensive data
        final_status = 'completed' if failed_count == 0 else 'partial'
        if sent_count == 0:
            final_status = 'failed'
        
        # Calculate rates
        total_recipients = sent_count + failed_count
        success_rate = (sent_count / total_recipients * 100) if total_recipients > 0 else 0
        
        cursor.execute('''
            UPDATE email_campaigns 
            SET status = ?, emails_sent = ?, emails_failed = ?, emails_pending = 0,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (final_status, sent_count, failed_count, campaign_id))
        
        # Log campaign completion event
        cursor.execute('''
            INSERT INTO campaign_analytics (id, campaign_id, event_type, metadata)
            VALUES (?, ?, 'campaign_completed', ?)
        ''', (str(uuid.uuid4()), campaign_id, json.dumps({
            'total_sent': sent_count,
            'total_failed': failed_count,
            'success_rate': success_rate,
            'final_status': final_status
        })))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error sending campaign {campaign_id}: {e}")
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE email_campaigns SET status = 'failed' WHERE id = ?
        ''', (campaign_id,))
        conn.commit()
        conn.close()

# ==============================
# Template Management Functions
# ==============================

def create_template(name, subject, html_content, text_content, category, created_by):
    """Create a new email template"""
    template_id = str(uuid.uuid4())
    
    # Convert plain text to HTML if needed
    if html_content and not html_content.strip().startswith('<!DOCTYPE'):
        # This appears to be plain text, convert to HTML
        converted_html = convert_text_to_html(html_content)
        text_content = html_content  # Store original as text_content
        html_content = converted_html
    
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO email_templates 
        (id, name, subject, html_content, text_content, category, created_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (template_id, name, subject, html_content, text_content or '', category, created_by))
    
    conn.commit()
    conn.close()
    
    return template_id

def get_template(template_id):
    """Get template details"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM email_templates WHERE id = ?', (template_id,))
    template = cursor.fetchone()
    
    if template:
        columns = [description[0] for description in cursor.description]
        conn.close()
        return dict(zip(columns, template))
    
    conn.close()
    return None

def get_all_templates():
    """Get all email templates"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, subject, html_content, text_content, category, created_at, is_active
        FROM email_templates 
        WHERE is_active = 1
        ORDER BY created_at DESC
    ''')
    
    templates = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    conn.close()
    return [dict(zip(columns, template)) for template in templates]

def get_campaign_statistics():
    """Get overall campaign statistics"""
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    # Get total campaigns
    cursor.execute('SELECT COUNT(*) FROM email_campaigns')
    total_campaigns = cursor.fetchone()[0]
    
    # Get total emails sent
    cursor.execute('SELECT SUM(emails_sent) FROM email_campaigns')
    total_sent = cursor.fetchone()[0] or 0
    
    # Get total recipients
    cursor.execute('SELECT SUM(total_recipients) FROM email_campaigns')
    total_recipients = cursor.fetchone()[0] or 0
    
    # Get success rate
    success_rate = (total_sent / total_recipients * 100) if total_recipients > 0 else 0
    
    # Get campaign status breakdown
    cursor.execute('''
        SELECT status, COUNT(*) 
        FROM email_campaigns 
        GROUP BY status
    ''')
    status_breakdown = dict(cursor.fetchall())
    
    # Get recent activity
    cursor.execute('''
        SELECT event_type, COUNT(*) 
        FROM campaign_analytics 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY event_type
    ''')
    recent_activity = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        'total_campaigns': total_campaigns,
        'total_sent': total_sent,
        'total_recipients': total_recipients,
        'success_rate': round(success_rate, 2),
        'status_breakdown': status_breakdown,
        'recent_activity': recent_activity
    }

def track_email_event(campaign_id, recipient_email, event_type, metadata=None, ip_address=None, user_agent=None):
    """Track email events like opens, clicks, bounces"""
    event_id = str(uuid.uuid4())
    
    conn = sqlite3.connect('eduops360.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO campaign_analytics 
        (id, campaign_id, event_type, recipient_email, ip_address, user_agent, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (event_id, campaign_id, event_type, recipient_email, ip_address, user_agent, 
          json.dumps(metadata) if metadata else None))
    
    # Update recipient record based on event type
    if event_type == 'opened':
        cursor.execute('''
            UPDATE campaign_recipients 
            SET opened_at = CURRENT_TIMESTAMP 
            WHERE campaign_id = ? AND email = ? AND opened_at IS NULL
        ''', (campaign_id, recipient_email))
    elif event_type == 'clicked':
        cursor.execute('''
            UPDATE campaign_recipients 
            SET clicked_at = CURRENT_TIMESTAMP 
            WHERE campaign_id = ? AND email = ?
        ''', (campaign_id, recipient_email))
    elif event_type == 'bounced':
        cursor.execute('''
            UPDATE campaign_recipients 
            SET bounced_at = CURRENT_TIMESTAMP, status = 'bounced'
            WHERE campaign_id = ? AND email = ?
        ''', (campaign_id, recipient_email))
    
    conn.commit()
    conn.close()
    
    return event_id

# ==============================
# Flask Routes
# ==============================

@campaigns_bp.route("/")
def campaigns_home():
    return render_template("email_campaigns.html", email_accounts=get_email_accounts())

@campaigns_bp.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    try:
        campaigns = get_all_campaigns()
        return jsonify({
            "success": True,
            "campaigns": campaigns,
            "count": len(campaigns)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns', methods=['POST'])
def create_campaign_endpoint():
    try:
        data = request.json
        
        campaign_id = create_campaign(
            name=data['name'],
            subject=data['subject'],
            template_id=data['template_id'],
            recipient_list=data['recipients'],
            email_account=data['email_account'],
            created_by=get_current_user_info()['id'] or 'admin',
            scheduled_at=data.get('scheduled_at')
        )
        
        return jsonify({
            "success": True,
            "campaign_id": campaign_id,
            "message": "Campaign created successfully"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns/<campaign_id>/send', methods=['POST'])
def send_campaign_endpoint(campaign_id):
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            return jsonify({
                "success": False,
                "error": "Campaign not found"
            }), 404
        
        if campaign['status'] != 'draft':
            return jsonify({
                "success": False,
                "error": "Campaign has already been sent or is in progress"
            }), 400
        
        # Start sending in background
        send_campaign(campaign_id)
        
        return jsonify({
            "success": True,
            "message": "Campaign sending started"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns/<campaign_id>', methods=['GET'])
def get_campaign_details(campaign_id):
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            return jsonify({
                "success": False,
                "error": "Campaign not found"
            }), 404
        
        return jsonify({
            "success": True,
            "campaign": campaign
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/templates', methods=['GET'])
def get_templates():
    try:
        templates = get_all_templates()
        return jsonify({
            "success": True,
            "templates": templates,
            "count": len(templates)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/templates', methods=['POST'])
def create_template_endpoint():
    try:
        data = request.json
        
        template_id = create_template(
            name=data['name'],
            subject=data['subject'],
            html_content=data['html_content'],
            text_content=data.get('text_content', ''),
            category=data.get('category', 'general'),
            created_by=get_current_user_info()['id'] or 'admin'
        )
        
        return jsonify({
            "success": True,
            "template_id": template_id,
            "message": "Template created successfully"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/templates/<template_id>', methods=['GET'])
def get_template_details(template_id):
    try:
        template = get_template(template_id)
        if not template:
            return jsonify({
                "success": False,
                "error": "Template not found"
            }), 404
        
        return jsonify({
            "success": True,
            "template": template
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/upload-recipients', methods=['POST'])
def upload_recipients():
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file uploaded"
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
            return jsonify({
                "success": False,
                "error": "Only Excel (.xlsx, .xls) and CSV files are allowed"
            }), 400
        
        # Save and process file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        
        # Read file based on extension
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # Process recipients
        recipients = []
        required_columns = ['email']
        
        # Check if required columns exist
        if not all(col in df.columns for col in required_columns):
            return jsonify({
                "success": False,
                "error": f"Required columns missing. File must contain: {', '.join(required_columns)}"
            }), 400
        
        for _, row in df.iterrows():
            if pd.notna(row['email']) and '@' in str(row['email']):
                recipient = {
                    'email': str(row['email']).strip(),
                    'name': str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                }
                recipients.append(recipient)
        
        # Clean up temp file
        os.remove(file_path)
        
        return jsonify({
            "success": True,
            "recipients": recipients,
            "count": len(recipients),
            "message": f"Successfully loaded {len(recipients)} recipients"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        stats = get_campaign_statistics()
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns/<campaign_id>/track/<event_type>', methods=['POST'])
def track_campaign_event(campaign_id, event_type):
    try:
        data = request.json or {}
        recipient_email = data.get('recipient_email')
        metadata = data.get('metadata')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        
        if not recipient_email:
            return jsonify({
                "success": False,
                "error": "Recipient email is required"
            }), 400
        
        event_id = track_email_event(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            event_type=event_type,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return jsonify({
            "success": True,
            "event_id": event_id,
            "message": f"Event '{event_type}' tracked successfully"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns/<campaign_id>/analytics', methods=['GET'])
def get_campaign_analytics(campaign_id):
    try:
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        
        # Get campaign analytics
        cursor.execute('''
            SELECT event_type, COUNT(*) as count
            FROM campaign_analytics 
            WHERE campaign_id = ?
            GROUP BY event_type
        ''', (campaign_id,))
        
        analytics = cursor.fetchall()
        analytics_dict = {row[0]: row[1] for row in analytics}
        
        # Get recipient status breakdown
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM campaign_recipients 
            WHERE campaign_id = ?
            GROUP BY status
        ''', (campaign_id,))
        
        status_breakdown = cursor.fetchall()
        status_dict = {row[0]: row[1] for row in status_breakdown}
        
        conn.close()
        
        return jsonify({
            "success": True,
            "analytics": analytics_dict,
            "status_breakdown": status_dict
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/campaigns/<campaign_id>/failed-emails-csv', methods=['GET'])
def get_failed_emails_csv(campaign_id):
    try:
        conn = sqlite3.connect('eduops360.db')
        cursor = conn.cursor()
        
        # Get failed recipients with error messages
        cursor.execute('''
            SELECT email, name, error_message, sent_at, retry_count
            FROM campaign_recipients 
            WHERE campaign_id = ? AND status = 'failed'
            ORDER BY email
        ''', (campaign_id,))
        
        failed_recipients = cursor.fetchall()
        
        if not failed_recipients:
            return jsonify({
                "success": False,
                "error": "No failed emails found for this campaign"
            }), 404
        
        # Create CSV content
        csv_content = "Email,Name,Failure Reason,Last Attempt,Retry Count\n"
        
        for recipient in failed_recipients:
            email, name, error_message, sent_at, retry_count = recipient
            
            # Clean up error message for better readability
            if error_message:
                # Simplify common error messages
                if "invalid" in error_message.lower() or "format" in error_message.lower():
                    simple_reason = "Invalid email format"
                elif "not found" in error_message.lower() or "does not exist" in error_message.lower():
                    simple_reason = "Email address does not exist"
                elif "full" in error_message.lower() or "quota" in error_message.lower():
                    simple_reason = "Recipient mailbox is full"
                elif "spam" in error_message.lower() or "blocked" in error_message.lower():
                    simple_reason = "Email blocked by spam filter"
                elif "timeout" in error_message.lower() or "unavailable" in error_message.lower():
                    simple_reason = "Email server temporarily unavailable"
                elif "authentication" in error_message.lower() or "auth" in error_message.lower():
                    simple_reason = "Email authentication failed"
                else:
                    simple_reason = "Email delivery failed"
            else:
                simple_reason = "Unknown error"
            
            # Format the CSV row
            name_clean = (name or "").replace('"', '""')  # Escape quotes
            csv_content += f'"{email}","{name_clean}","{simple_reason}","{sent_at or "Not attempted"}","{retry_count or 0}"\n'
        
        conn.close()
        
        # Create response with CSV content
        from flask import Response
        
        response = Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=campaign_{campaign_id}_failed_emails.csv'
            }
        )
        
        return response
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@campaigns_bp.route('/api/clear-all-data', methods=['POST'])
def clear_all_data():
    """Clear all campaigns and templates - DANGER: This deletes everything!"""
    try:
        success = clear_all_campaigns_and_templates()
        
        if success:
            return jsonify({
                "success": True,
                "message": "All campaigns and templates have been deleted successfully!"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to clear database"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
