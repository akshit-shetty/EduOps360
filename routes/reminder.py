# reminder.py
from flask import Flask, jsonify, request, send_file,render_template, Blueprint
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import re
import os
import requests
from io import BytesIO
import urllib.parse
import json
import threading
from functools import wraps
import tempfile
import sqlite3
import shutil
from werkzeug.utils import secure_filename
from auth.email_utils import SMTPEmailSender, send_smtp_email, get_available_email_accounts
from auth.email_config import get_email_accounts
from utils.database import get_db_connection, execute_query


reminders_bp = Blueprint("reminder", __name__)
CORS(reminders_bp)

# Storage directories
REMINDER_STORAGE_DIR = "reminder_storage"
UPLOADED_FILES_DIR = os.path.join(REMINDER_STORAGE_DIR, "uploaded_files")

# Ensure storage directories exist
os.makedirs(REMINDER_STORAGE_DIR, exist_ok=True)
os.makedirs(UPLOADED_FILES_DIR, exist_ok=True)

@reminders_bp.route("/")
def reminder_home():
    # Load persistent data on page load
    load_persistent_data()
    return render_template("reminder.html", email_accounts=get_email_accounts())

# Global state to track email sending progress
email_status = {}
sessions_data = []
uploaded_file_path = None

def run_in_thread(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return decorated_function

# ==============================
# Email validation helper
# ==============================
def is_valid_email(email):
    if pd.isna(email):
        return False
    email = str(email).strip()
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

# ==============================
# Database Functions
# ==============================
def setup_reminder_database():
    """Setup database tables for reminder storage with Cohort column"""
    try:
        # Create reminder sessions table with Cohort column
        create_sessions_table = '''
            CREATE TABLE IF NOT EXISTS reminder_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT NOT NULL,
                professor_email TEXT NOT NULL,
                session_date TEXT NOT NULL,
                session_time TEXT NOT NULL,
                session_topic TEXT NOT NULL,
                zoom_link TEXT,
                drive_link TEXT,
                cohort TEXT,
                learner_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_name TEXT,
                file_path TEXT
            )
        '''
        execute_query(create_sessions_table)
        
        # Create email status table for persistence
        create_email_status_table = '''
            CREATE TABLE IF NOT EXISTS reminder_email_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_email TEXT NOT NULL UNIQUE,
                professor_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                message TEXT,
                recipient_type TEXT DEFAULT 'professors',
                sent_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress_total INTEGER DEFAULT 0,
                progress_completed INTEGER DEFAULT 0
            )
        '''
        execute_query(create_email_status_table)
        
        # Create reminder files table
        create_files_table = '''
            CREATE TABLE IF NOT EXISTS reminder_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        '''
        execute_query(create_files_table)
        
        print("✅ Reminder database tables ready with Cohort column")
        
    except Exception as e:
        print(f"❌ Error setting up reminder database: {e}")

def save_sessions_to_database(sessions_data, file_info):
    """Save sessions data to database"""
    try:
        print(f"🔄 Starting database save for {len(sessions_data)} professors...")
        
        # Clear existing sessions (only keep latest upload)
        execute_query("DELETE FROM reminder_sessions")
        print(f"🗑️ Cleared existing sessions from database")
        
        total_sessions = 0
        # Insert new sessions with cohort information
        for professor in sessions_data:
            prof_name = professor["professor"]
            prof_email = professor["email"]
            print(f"💾 Saving professor: {prof_name} ({prof_email}) with {len(professor['sessions'])} sessions")
            
            for session in professor["sessions"]:
                total_sessions += 1
                execute_query('''
                    INSERT INTO reminder_sessions 
                    (professor_name, professor_email, session_date, session_time, 
                     session_topic, zoom_link, drive_link, cohort, learner_time, file_name, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prof_name, prof_email, session["date"], session["time"],
                    session["topic"], session["link"], session.get("drive", ""),
                    session.get("cohort", "Unknown Cohort"), session.get("learner_time", session["time"]),
                    file_info["original_filename"], file_info["stored_path"]
                ))
        
        print(f"✅ Saved {len(sessions_data)} professors with {total_sessions} total sessions to database")
        
        # Verify the save
        count_check = execute_query("SELECT COUNT(*) as count FROM reminder_sessions", fetch='one')
        print(f"🔍 Database verification: {count_check['count']} sessions now in database")
        
    except Exception as e:
        print(f"❌ Error saving sessions to database: {e}")
        import traceback
        traceback.print_exc()

def save_file_to_storage(uploaded_file):
    """Save uploaded file to storage"""
    try:
        # Generate secure filename
        original_filename = secure_filename(uploaded_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_{original_filename}"
        stored_path = os.path.join(UPLOADED_FILES_DIR, stored_filename)
        
        # Save file
        uploaded_file.save(stored_path)
        
        # Save file info to database
        execute_query('''
            UPDATE reminder_files SET is_active = FALSE WHERE is_active = TRUE
        ''')
        
        execute_query('''
            INSERT INTO reminder_files (original_filename, stored_filename, file_path)
            VALUES (?, ?, ?)
        ''', (original_filename, stored_filename, stored_path))
        
        print(f"✅ File saved to storage: {stored_path}")
        
        return {
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "stored_path": stored_path
        }
        
    except Exception as e:
        print(f"❌ Error saving file to storage: {e}")
        return None

def load_persistent_data():
    """Load sessions data from database on application start"""
    global sessions_data, uploaded_file_path, email_status
    
    try:
        # Setup database if needed
        setup_reminder_database()
        
        # Load sessions from database
        sessions_rows = execute_query('''
            SELECT DISTINCT professor_name, professor_email, file_name, file_path
            FROM reminder_sessions
            ORDER BY professor_name
        ''', fetch='all')
        
        if not sessions_rows:
            print("ℹ️ No persistent sessions data found")
            return
        
        # Reconstruct sessions_data structure
        sessions_data.clear()
        professors_dict = {}
        
        # Get all session details including cohort
        all_sessions = execute_query('''
            SELECT professor_name, professor_email, session_date, session_time,
                   session_topic, zoom_link, drive_link, cohort, learner_time, file_name, file_path
            FROM reminder_sessions
            ORDER BY professor_name, session_date, session_time
        ''', fetch='all')
        
        for session_row in all_sessions:
            prof_name = session_row['professor_name']
            prof_email = session_row['professor_email']
            
            if prof_name not in professors_dict:
                professors_dict[prof_name] = {
                    "professor": prof_name,
                    "email": prof_email,
                    "sessions": []
                }
            
            professors_dict[prof_name]["sessions"].append({
                "date": session_row['session_date'],
                "time": session_row['session_time'],
                "learner_time": session_row['learner_time'] or session_row['session_time'],
                "topic": session_row['session_topic'],
                "link": session_row['zoom_link'],
                "drive": session_row['drive_link'] or "",
                "cohort": session_row['cohort'] or "Unknown Cohort"
            })
        
        sessions_data.extend(professors_dict.values())
        
        # Set uploaded file path to the most recent file
        if sessions_rows:
            uploaded_file_path = sessions_rows[0]['file_path']
        
        # Load email status from database
        load_email_status_from_database()
        
        total_sessions = sum(len(prof["sessions"]) for prof in sessions_data)
        print(f"✅ Loaded {len(sessions_data)} professors with {total_sessions} sessions from database")
        
    except Exception as e:
        print(f"❌ Error loading persistent data: {e}")

def save_email_status_to_database():
    """Save current email status to database for persistence"""
    global email_status, sessions_data
    
    try:
        # Clear existing status
        execute_query("DELETE FROM reminder_email_status")
        
        # Save current email status
        for email, status_info in email_status.items():
            execute_query('''
                INSERT INTO reminder_email_status 
                (professor_email, professor_name, status, message, recipient_type, sent_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                email,
                status_info.get("professor", "Unknown"),
                status_info.get("status", "pending"),
                status_info.get("message", ""),
                status_info.get("recipient_type", "professors"),
                status_info.get("sent_at")
            ))
        
        print(f"✅ Saved {len(email_status)} email statuses to database")
        
    except Exception as e:
        print(f"❌ Error saving email status to database: {e}")

def load_email_status_from_database():
    """Load email status from database on page load"""
    global email_status
    
    try:
        status_rows = execute_query('''
            SELECT professor_email, professor_name, status, message, recipient_type, sent_at
            FROM reminder_email_status
            ORDER BY updated_at DESC
        ''', fetch='all')
        
        if status_rows:
            email_status.clear()
            for row in status_rows:
                email_status[row['professor_email']] = {
                    "professor": row['professor_name'],
                    "status": row['status'],
                    "message": row['message'],
                    "recipient_type": row['recipient_type'],
                    "sent_at": row['sent_at']
                }
            
            print(f"✅ Loaded {len(email_status)} email statuses from database")
        else:
            print("ℹ️ No email status data found in database")
            
    except Exception as e:
        print(f"❌ Error loading email status from database: {e}")

def update_email_status_in_database(email, status, message, recipient_type="professors"):
    """Update individual email status in database"""
    global email_status
    
    try:
        # Update in-memory status
        if email not in email_status:
            email_status[email] = {}
        
        email_status[email].update({
            "status": status,
            "message": message,
            "recipient_type": recipient_type,
            "sent_at": datetime.now().isoformat() if status == "sent" else None
        })
        
        # Update database
        execute_query('''
            INSERT OR REPLACE INTO reminder_email_status 
            (professor_email, professor_name, status, message, recipient_type, sent_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            email,
            email_status[email].get("professor", "Unknown"),
            status,
            message,
            recipient_type,
            email_status[email].get("sent_at")
        ))
        
        print(f"📧 Updated status for {email}: {status} - {message}")
        
    except Exception as e:
        print(f"❌ Error updating email status in database: {e}")

def clear_persistent_data():
    """Clear all reminder data from database"""
    global sessions_data, uploaded_file_path, email_status
    
    try:
        # Clear database tables
        execute_query("DELETE FROM reminder_sessions")
        execute_query("DELETE FROM reminder_files")
        execute_query("DELETE FROM reminder_email_status")
        
        # Clear global variables
        sessions_data.clear()
        uploaded_file_path = None
        email_status.clear()
        
        # Clear uploaded files directory
        if os.path.exists(UPLOADED_FILES_DIR):
            for filename in os.listdir(UPLOADED_FILES_DIR):
                file_path = os.path.join(UPLOADED_FILES_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
        
        print("✅ All reminder data cleared from database")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing persistent data: {e}")
        return False

# ==============================
# Load sessions from uploaded Excel file
# ==============================
def load_sessions_from_excel(file_path):
    global sessions_data, email_status
    
    print("🔍 Starting Excel session loading...")
    
    try:
        print("📊 Reading Excel file...")
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            print("✅ Excel file loaded with openpyxl engine")
        except Exception as e:
            print(f"❌ Openpyxl failed: {e}. Trying xlrd...")
            try:
                df = pd.read_excel(file_path, engine='xlrd')
                print("✅ Excel file loaded with xlrd engine")
            except Exception as e2:
                print(f"❌ xlrd failed: {e2}. Trying default engine...")
                df = pd.read_excel(file_path)
                print("✅ Excel file loaded with default engine")
        
        print(f"📋 Loaded DataFrame shape: {df.shape}")
        print(f"📋 Columns: {list(df.columns)}")
        
        # Check if we have data
        if df.empty:
            print("⚠️ DataFrame is empty after loading")
            return []
            
        # Convert Date column to datetime
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        print(f"📅 Date conversion - NaN count: {df['Date'].isna().sum()}")

        # Strip whitespace from emails (avoid duplicates)
        df["Email"] = df["Email"].astype(str).str.strip()

        # ==============================
        # Calculate THIS or NEXT weekend (Fri–Sun)
        # ==============================
        today = datetime.today().date()

        if today.weekday() >= 4:  # Friday (4), Saturday (5), Sunday (6)
            next_friday = today - timedelta(days=today.weekday() - 4)  # This Friday
        else:
            days_ahead = (4 - today.weekday() + 7) % 7  # Find upcoming Friday
            next_friday = today + timedelta(days=days_ahead)

        end_of_weekend = next_friday + timedelta(days=2)

        # ==============================
        # Filter for sessions in weekend
        # ==============================
        df = df[(df['Date'].dt.date >= next_friday) & (df['Date'].dt.date <= end_of_weekend)]

        if df.empty:
            return []

        # ==============================
        # Group by professor email and format data
        # ==============================
        professor_groups = df.groupby(["SME_Prof_Name", "Email"])
        
        sessions_data = []
        for (prof_name, email), group in professor_groups:
            professor_sessions = []
            
            for _, row in group.iterrows():
                drive_link = row["Drive link"]
                print(f"DEBUG: Original drive link from Excel: '{drive_link}' (type: {type(drive_link)})")
                
                if pd.isna(drive_link):
                    drive_link = ""
                    print("DEBUG: Drive link was NaN, set to empty string")
                else:
                    drive_link = str(drive_link).strip()
                    # If it's empty after stripping or contains only whitespace, set to empty
                    if not drive_link or drive_link.isspace():
                        drive_link = ""
                        print("DEBUG: Drive link was empty/whitespace, set to empty string")
                    else:
                        print(f"DEBUG: Drive link after processing: '{drive_link}'")

                # Extract cohort information
                cohort = row.get("Cohort", "Unknown Cohort")
                if pd.isna(cohort) or not str(cohort).strip():
                    cohort = "Unknown Cohort"
                else:
                    cohort = str(cohort).strip()

                session = {
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "time": row.get("ProfessorTime", "Time TBD"),
                    "learner_time": row.get("Learner Time", row.get("ProfessorTime", "Time TBD")),
                    "topic": row["Topic"],
                    "link": row.get("Session_Link", ""),
                    "drive": drive_link,
                    "cohort": cohort
                }
                professor_sessions.append(session)
            
            sessions_data.append({
                "professor": prof_name,
                "email": email,
                "sessions": professor_sessions
            })
            
            # Initialize email status
            if email not in email_status:
                email_status[email] = {
                    "professor": prof_name,
                    "status": "pending",
                    "message": "Not sent yet"
                }
        
        return sessions_data

    except Exception as e:
        print(f"❌ Error in load_sessions_from_excel: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

# ==============================
# Send emails function
# ==============================
@run_in_thread
def send_emails(preview_only=False, recipient_type="professors", email_account="primary"):
    global email_status, sessions_data
    
    print(f"🎯 SEND_EMAILS: recipient_type='{recipient_type}', preview_only={preview_only}")
    
    try:
        # Initialize SMTP email sender with selected account
        from auth.email_utils import send_smtp_email
        print(f"🔧 Using email account: {email_account}")
        
        # Validate email account
        from auth.email_config import get_account_by_key
        selected_account = get_account_by_key(email_account)
        if not selected_account:
            raise Exception(f"Email account '{email_account}' not found or not configured.")
        
        # Create preview folder if needed
        preview_folder = "Email_Previews"
        if preview_only and not os.path.exists(preview_folder):
            os.makedirs(preview_folder)
        
        # Determine recipients based on type
        if recipient_type == "learners":
            # Send consolidated email to admin for learner forwarding
            admin_email = "akshit1.shetty@upgrad.com"
            send_student_reminder_email(admin_email, sessions_data, preview_only, email_account)
        else:
            # Process each professor (original functionality)
            for professor in sessions_data:
                prof_name = professor["professor"]
                email = professor["email"]
                
                if not is_valid_email(email):
                    email_status[email] = {
                        "professor": prof_name,
                        "status": "error",
                        "message": "Invalid email address"
                    }
                    continue
                
                send_professor_reminder_email(professor, preview_only, email_account)
    
    except Exception as e:
        print(f"Error in email sending: {e}")
        # Update all remaining emails as failed
        for professor in sessions_data:
            email = professor["email"]
            if email not in email_status:
                email_status[email] = {
                    "professor": professor["professor"],
                    "status": "error",
                    "message": f"Email sending failed: {str(e)}"
                }

def send_professor_reminder_email(professor, preview_only, email_account):
    """Send reminder email to individual professor"""
    global email_status
    
    prof_name = professor["professor"]
    email = professor["email"]
    
    try:
        # Subject
        subject = f"Reminder: Upcoming Live Sessions This Weekend for {prof_name}"
        
        # HTML Email body
        body = f"""
        <p>Hello <b>{prof_name}</b>,</p>
        <p>I hope this message finds you well. This is a gentle reminder regarding your upcoming sessions scheduled for this weekend.</p>
        <p><b>Session Details:</b></p>
        """
        
        for i, session in enumerate(professor["sessions"], 1):
            session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%B %d, %Y, %A")
            body += f"""
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;">
                <h4 style="margin: 0 0 10px 0; color: #1e40af; font-weight: bold;">Session {i}</h4>
                <p style="margin: 5px 0;"><strong>Date:</strong> {session_date}</p>
                <p style="margin: 5px 0;"><strong>Time:</strong> {session['time']}</p>
                <p style="margin: 5px 0;"><strong>Topic:</strong> {session['topic']}</p>
                <p style="margin: 5px 0;"><strong>Zoom Meeting:</strong> <a href="{session['link']}" style="color: #3b82f6; text-decoration: underline;">Join Meeting</a></p>
            """
            
            drive_link = session["drive"]
            print(f"DEBUG: Drive link for {prof_name}: '{drive_link}' (type: {type(drive_link)})")
            
            if drive_link and isinstance(drive_link, str) and drive_link.strip() and not drive_link.isspace():
                print(f"DEBUG: Adding drive link: {drive_link}")
                body += f'<p style="margin: 5px 0;"><strong>Drive Link:</strong> <a href="{drive_link}" style="color: #10b981; text-decoration: underline;">Upload PPTs/Materials</a></p>'
            else:
                print(f"DEBUG: No valid drive link found, showing default message")
                body += '<p style="margin: 5px 0; color: #dc2626;"><strong>Note:</strong> Kindly share the PPTs or materials that need to be shared with the learners in this email.</p>'
            
            body += "</div>"
        
        body += """
        <p>Please let us know if you require any assistance or have any updates regarding the session. 
        We look forward to a successful weekend of learning!</p>
        <p><strong>Best regards,</strong><br>Operations Team</p>
        """
        
        if preview_only:
            # Create preview folder if needed
            preview_folder = "Email_Previews"
            if not os.path.exists(preview_folder):
                os.makedirs(preview_folder)
            
            # Save preview as HTML file instead of .msg
            preview_path = os.path.join(preview_folder, f"{prof_name}_{email}.html".replace(" ", "_"))
            with open(preview_path, 'w', encoding='utf-8') as f:
                f.write(f"""
                <html>
                <head><title>{subject}</title></head>
                <body>
                <h3>Email Preview</h3>
                <p><strong>To:</strong> {email}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <hr>
                {body}
                </body>
                </html>
                """)
            # Update status in database
            update_email_status_in_database(email, "preview", f"Preview saved: {preview_path}", "professors")
        else:
            try:
                # Send email using SMTP with selected account
                from auth.email_utils import send_smtp_email
                result = send_smtp_email(
                    to_email=email,
                    subject=subject,
                    html_body=body,
                    account_key=email_account
                )
                
                if result['success']:
                    # Update status in database
                    update_email_status_in_database(email, "sent", f"Email sent successfully to {prof_name}", "professors")
                else:
                    # Update status in database
                    update_email_status_in_database(email, "error", result['message'], "professors")
            except Exception as e:
                # Update status in database
                update_email_status_in_database(email, "error", f"Failed to send email: {str(e)}", "professors")
    
    except Exception as e:
        print(f"Error sending professor email: {e}")
        # Update status in database
        update_email_status_in_database(email, "error", f"Email sending failed: {str(e)}", "professors")

def send_student_reminder_email(admin_email, sessions_data, preview_only, email_account):
    """Send separate reminder emails for each cohort to admin for student forwarding"""
    global email_status
    
    try:
        # Group sessions by cohort using the "Cohort Name - Track" column from Excel
        cohort_sessions = {}
        
        for professor in sessions_data:
            prof_name = professor["professor"]
            for session in professor["sessions"]:
                # Get cohort name directly from the Excel column
                cohort_name = session.get("cohort", "Unknown Cohort")
                
                if cohort_name not in cohort_sessions:
                    cohort_sessions[cohort_name] = []
                
                cohort_sessions[cohort_name].append({
                    "session": session,
                    "professor": prof_name
                })
        
        # Send separate email for each cohort
        for cohort_name, sessions in cohort_sessions.items():
            send_cohort_reminder_email(admin_email, cohort_name, sessions, preview_only, email_account)
            
    except Exception as e:
        print(f"Error sending student reminder email: {e}")
        # Update status for all professors as failed
        for professor in sessions_data:
            email_status[professor["email"]] = {
                "professor": professor["professor"],
                "status": "error",
                "message": f"Student reminder failed: {str(e)}"
            }


def send_cohort_reminder_email(admin_email, cohort_name, sessions, preview_only, email_account):
    """Send reminder email for a specific cohort"""
    global email_status, sessions_data
    
    try:
        # Subject for specific cohort
        subject = f"Reminder: {cohort_name} - Upcoming Live Sessions This Weekend"
        
        # HTML Email body for learners
        body = f"""
        <p>Dear {cohort_name} Learners,</p>
        <p>Greetings from upGrad!</p>
        <p>We hope this message finds you in good health and high spirits. We are writing to remind you about the upcoming live sessions scheduled for this weekend.</p>
        """
        
        # Group sessions by day
        saturday_sessions = []
        sunday_sessions = []
        other_sessions = []
        
        for session_data in sessions:
            session = session_data["session"]
            session_date = datetime.strptime(session["date"], "%Y-%m-%d")
            weekday = session_date.weekday()
            
            if weekday == 5:  # Saturday
                saturday_sessions.append(session_data)
            elif weekday == 6:  # Sunday
                sunday_sessions.append(session_data)
            else:
                other_sessions.append(session_data)
        
        # Add Saturday sessions
        body += "<p><strong>Sessions on Saturday:</strong></p>"
        if saturday_sessions:
            for session_data in saturday_sessions:
                session = session_data["session"]
                professor = session_data["professor"]
                session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
                
                body += f"""
                <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #3b82f6; background-color: #f8fafc;">
                    <p><strong>Date:</strong> {session_date}</p>
                    <p><strong>Time:</strong> {session['time']}</p>
                    <p><strong>Topic:</strong> {session['topic']}</p>
                    <p><strong>Conducted by:</strong> {professor}</p>
                    <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #3b82f6; text-decoration: underline;">{session['link']}</a></p>
                </div>
                """
        else:
            body += """
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
                <p style="color: #d97706; font-weight: bold;">No Live sessions scheduled on Saturday</p>
            </div>
            """
        
        # Add Sunday sessions
        body += "<p><strong>Sessions on Sunday:</strong></p>"
        if sunday_sessions:
            for session_data in sunday_sessions:
                session = session_data["session"]
                professor = session_data["professor"]
                session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
                
                body += f"""
                <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #10b981; background-color: #f0fdf4;">
                    <p><strong>Date:</strong> {session_date}</p>
                    <p><strong>Time:</strong> {session['time']}</p>
                    <p><strong>Topic:</strong> {session['topic']}</p>
                    <p><strong>Conducted by:</strong> {professor}</p>
                    <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #10b981; text-decoration: underline;">{session['link']}</a></p>
                </div>
                """
        else:
            body += """
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
                <p style="color: #d97706; font-weight: bold;">No Live sessions scheduled on Sunday</p>
            </div>
            """
        
        # Add other day sessions if any
        if other_sessions:
            body += "<p><strong>Other Sessions:</strong></p>"
            for session_data in other_sessions:
                session = session_data["session"]
                professor = session_data["professor"]
                session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
                
                body += f"""
                <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
                    <p><strong>Date:</strong> {session_date}</p>
                    <p><strong>Time:</strong> {session['time']}</p>
                    <p><strong>Topic:</strong> {session['topic']}</p>
                    <p><strong>Conducted by:</strong> {professor}</p>
                    <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #f59e0b; text-decoration: underline;">{session['link']}</a></p>
                </div>
                """
        
        # Add World Time Buddy link
        body += """
        <div style="margin-top: 30px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f1f5f9;">
            <p><strong>Time Zone Converter:</strong></p>
            <p>Below is the link for World Time Buddy. You can set the time according to your local time zone:</p>
            <p><a href="https://www.worldtimebuddy.com/" style="color: #3b82f6; text-decoration: underline;">https://www.worldtimebuddy.com/</a></p>
        </div>
        
        <p style="margin-top: 20px;"><strong>Best regards,</strong><br>
        <strong>upGrad Team</strong></p>
        """
        
        if preview_only:
            # Create preview folder if needed
            preview_folder = "Email_Previews"
            if not os.path.exists(preview_folder):
                os.makedirs(preview_folder)
            
            # Save preview as HTML file with cohort name
            safe_cohort_name = cohort_name.replace(" ", "_").replace("/", "_")
            preview_path = os.path.join(preview_folder, f"Student_Reminder_{safe_cohort_name}_{admin_email}.html")
            with open(preview_path, 'w', encoding='utf-8') as f:
                f.write(f"""
                <html>
                <head><title>{subject}</title></head>
                <body>
                <h3>Email Preview - Student Reminder for {cohort_name}</h3>
                <p><strong>To:</strong> {admin_email}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <hr>
                {body}
                </body>
                </html>
                """)
            
            # Update status for sessions in this cohort
            for session_data in sessions:
                session = session_data["session"]
                professor = session_data["professor"]
                # Find the professor email from sessions_data
                for prof_data in sessions_data:
                    if prof_data["professor"] == professor:
                        # Update status in database
                        update_email_status_in_database(prof_data["email"], "preview", f"Student reminder preview saved for {cohort_name}: {preview_path}", "learners")
                        break
        else:
            try:
                # Send email using SMTP with selected account
                from auth.email_utils import send_smtp_email
                result = send_smtp_email(
                    to_email=admin_email,
                    subject=subject,
                    html_body=body,
                    account_key=email_account
                )
                
                if result['success']:
                    # Update status for sessions in this cohort
                    for session_data in sessions:
                        session = session_data["session"]
                        professor = session_data["professor"]
                        # Find the professor email from sessions_data
                        for prof_data in sessions_data:
                            if prof_data["professor"] == professor:
                                # Update status in database
                                update_email_status_in_database(prof_data["email"], "sent", f"Student reminder sent for {cohort_name} to {admin_email}", "learners")
                                break
                else:
                    # Update status for sessions in this cohort as failed
                    for session_data in sessions:
                        session = session_data["session"]
                        professor = session_data["professor"]
                        # Find the professor email from sessions_data
                        for prof_data in sessions_data:
                            if prof_data["professor"] == professor:
                                # Update status in database
                                update_email_status_in_database(prof_data["email"], "error", f"Failed to send student reminder for {cohort_name}: {result['message']}", "learners")
                                break
            except Exception as e:
                # Update status for sessions in this cohort as failed
                for session_data in sessions:
                    session = session_data["session"]
                    professor = session_data["professor"]
                    # Find the professor email from sessions_data
                    for prof_data in sessions_data:
                        if prof_data["professor"] == professor:
                            # Update status in database
                            update_email_status_in_database(prof_data["email"], "error", f"Failed to send student reminder for {cohort_name}: {str(e)}", "learners")
                            break
    
    except Exception as e:
        print(f"Error sending cohort reminder email for {cohort_name}: {e}")
        # Update status for sessions in this cohort as failed
        for session_data in sessions:
            session = session_data["session"]
            professor = session_data["professor"]
            # Find the professor email from sessions_data
            for prof_data in sessions_data:
                if prof_data["professor"] == professor:
                    # Update status in database
                    update_email_status_in_database(prof_data["email"], "error", f"Cohort reminder failed for {cohort_name}: {str(e)}", "learners")
                    break

# ==============================
# Flask Routes
# ==============================

# Add this after your existing /api/upload-excel POST endpoint
@reminders_bp.route('/api/upload-excel', methods=['GET'])
def get_sessions():
    try:
        return jsonify({
            "success": True,
            "sessions": sessions_data,
            "count": len(sessions_data),
            "message": f"Loaded {len(sessions_data)} professors" if sessions_data else "No sessions loaded"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@reminders_bp.route('/api/upload-excel', methods=['POST'])
def upload_excel():
    global uploaded_file_path, sessions_data
    
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
    
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return jsonify({
            "success": False,
            "error": "Only Excel files are allowed"
        }), 400
    
    try:
        # Save file to persistent storage
        file_info = save_file_to_storage(file)
        if not file_info:
            return jsonify({
                "success": False,
                "error": "Failed to save file to storage"
            }), 500
        
        uploaded_file_path = file_info["stored_path"]
        
        # Load sessions from the uploaded file
        sessions = load_sessions_from_excel(file_info["stored_path"])
        
        if sessions:
            print(f"📊 About to save {len(sessions)} professors to database...")
            # Save sessions to database for persistence
            save_sessions_to_database(sessions, file_info)
            
            # Update global sessions_data
            sessions_data.clear()
            sessions_data.extend(sessions)
            print(f"✅ Updated global sessions_data with {len(sessions_data)} professors")
        else:
            print("❌ No sessions to save - sessions list is empty")
        
        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "message": f"Successfully loaded and saved {len(sessions)} professors to database",
            "file_info": {
                "original_name": file_info["original_filename"],
                "stored_name": file_info["stored_filename"]
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@reminders_bp.route('/api/debug-sessions', methods=['GET'])
def debug_sessions():
    debug_info = []
    for professor in sessions_data:
        for session in professor["sessions"]:
            debug_info.append({
                "professor": professor["professor"],
                "drive_link": session["drive"],
                "drive_link_type": type(session["drive"]).__name__,
                "drive_link_is_empty": not session["drive"] if session["drive"] else True
            })
    return jsonify(debug_info)

@reminders_bp.route('/api/email-status', methods=['GET'])
def get_email_status():
    """Get current email status with real-time updates"""
    try:
        # Load latest status from database
        load_email_status_from_database()
        
        # Calculate progress statistics
        total_professors = len(sessions_data)
        sent_count = sum(1 for status in email_status.values() if status.get("status") == "sent")
        error_count = sum(1 for status in email_status.values() if status.get("status") == "error")
        pending_count = total_professors - sent_count - error_count
        
        progress_percentage = (sent_count + error_count) / total_professors * 100 if total_professors > 0 else 0
        
        return jsonify({
            "success": True,
            "email_status": email_status,
            "progress": {
                "total": total_professors,
                "sent": sent_count,
                "error": error_count,
                "pending": pending_count,
                "percentage": round(progress_percentage, 1)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "email_status": email_status
        })

@reminders_bp.route('/api/stats', methods=['GET'])
def get_stats():
    professor_count = len(sessions_data)
    
    total_sessions = 0
    for professor in sessions_data:
        total_sessions += len(professor["sessions"])
    
    sent_count = sum(1 for status in email_status.values() if status["status"] == "sent")
    error_count = sum(1 for status in email_status.values() if status["status"] == "error")
    
    return jsonify({
        "professors": professor_count,
        "sessions": total_sessions,
        "emails_sent": sent_count,
        "errors": error_count
    })



@reminders_bp.route('/api/send-emails', methods=['POST'])
def send_emails_endpoint():
    data = request.json
    preview_only = data.get('preview', False)
    recipient_type = data.get('recipient_type', 'professors')
    email_account = data.get('email_account', 'primary')
    
    if not sessions_data:
        return jsonify({
            "success": False,
            "error": "No sessions loaded. Please upload an Excel file first."
        }), 400
    
    # Validate email account
    from auth.email_config import get_account_by_key
    selected_account = get_account_by_key(email_account)
    if not selected_account:
        return jsonify({
            "success": False,
            "error": f"Email account '{email_account}' not found or not configured."
        }), 400
    
    send_emails(preview_only=preview_only, recipient_type=recipient_type, email_account=email_account)
    
    message = f"Email sending process started using {selected_account.name}"
    if recipient_type == "learners":
        message += " (sending to admin for learner forwarding)"
    
    return jsonify({
        "success": True,
        "message": message
    })

@reminders_bp.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset all reminder data including database storage"""
    try:
        success = clear_persistent_data()
        if success:
            return jsonify({
                "success": True,
                "message": "All reminder data cleared successfully from database"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to clear data from database"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to reset data: {str(e)}"
        }), 500

@reminders_bp.route('/api/test-email', methods=['POST'])
def test_email():
    """Test email functionality"""
    try:
        data = request.json
        email_account = data.get('email_account', 'primary')
        test_email = data.get('test_email', 'akshit1.shetty@upgrad.com')
        
        from auth.email_utils import send_smtp_email
        result = send_smtp_email(
            to_email=test_email,
            subject="EduOps360 Session Reminder - Test Email",
            html_body="<p>This is a test email from EduOps360 Session Reminder system.</p><p>If you receive this, the email system is working correctly!</p>",
            account_key=email_account
        )
        
        return jsonify({
            "success": result['success'],
            "message": result['message']
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@reminders_bp.route('/api/preview-email/<email>', methods=['GET'])
def preview_email(email):
    # Get preview type from query parameter
    preview_type = request.args.get('type', 'professors')
    
    # Find the professor with this email
    professor = next((p for p in sessions_data if p["email"] == email), None)
    
    if not professor:
        return jsonify({
            "success": False,
            "error": "Professor not found"
        }), 404
    
    if preview_type == "learners":
        html = generate_learner_preview(professor)
    else:
        html = generate_professor_preview(professor, email)
    
    return jsonify({
        "success": True,
        "preview": html,
        "type": preview_type
    })

def generate_professor_preview(professor, email):
    """Generate professor email preview"""
    prof_name = professor["professor"]
    
    html = f"""
    <div style="margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
        <div class="mb-4 p-4 bg-blue-50 rounded-lg">
            <p><strong>To:</strong> {prof_name} &lt;{email}&gt;</p>
            <p><strong>Subject:</strong> Reminder: Upcoming Live Sessions This Weekend for {prof_name}</p>
            <p><strong>Type:</strong> <span class="text-blue-600 font-semibold">Professor Email</span></p>
        </div>
        <div class="email-preview">
            <p>Hello <b>{prof_name}</b>,</p>
            <p>I hope this message finds you well. This is a gentle reminder regarding your upcoming sessions scheduled for this weekend.</p>
            <p><b>Session Details:</b></p>
    """
    
    for i, session in enumerate(professor["sessions"], 1):
        session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%B %d, %Y, %A")
        html += f"""
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;">
                <h4 style="margin: 0 0 10px 0; color: #1e40af; font-weight: bold;">Session {i}</h4>
                <p style="margin: 5px 0;"><strong>Date:</strong> {session_date}</p>
                <p style="margin: 5px 0;"><strong>Time:</strong> {session['time']}</p>
                <p style="margin: 5px 0;"><strong>Topic:</strong> {session['topic']}</p>
                <p style="margin: 5px 0;"><strong>Zoom Meeting:</strong> <a href="{session['link']}" style="color: #3b82f6; text-decoration: underline;">Join Meeting</a></p>
        """
        
        drive_link = session["drive"]
        if drive_link and isinstance(drive_link, str) and drive_link.strip() and not drive_link.isspace():
            html += f'<p style="margin: 5px 0;"><strong>Drive Link:</strong> <a href="{drive_link}" style="color: #10b981; text-decoration: underline;">Upload PPTs/Materials</a></p>'
        else:
            html += '<p style="margin: 5px 0; color: #dc2626;"><strong>Note:</strong> Kindly share the PPTs or materials that need to be shared with the learners in this email.</p>'
        
        html += "</div>"
    
    html += """
            <p>Please let us know if you require any assistance or have any updates regarding the session. 
            We look forward to a successful weekend of learning!</p>
            <p><strong>Best regards,</strong><br>Operations Team</p>
        </div>
    </div>
    """
    return html

def generate_learner_preview(professor):
    """Generate learner email preview (cohort-based format)"""
    # Get cohort from the professor's sessions
    cohort_name = "Unknown Cohort"
    if professor["sessions"]:
        cohort_name = professor["sessions"][0].get("cohort", "Unknown Cohort")
    
    admin_email = "akshit1.shetty@upgrad.com"
    
    # Group sessions by day
    saturday_sessions = []
    sunday_sessions = []
    other_sessions = []
    
    for session in professor["sessions"]:
        session_date = datetime.strptime(session["date"], "%Y-%m-%d")
        day_of_week = session_date.weekday()
        
        session_data = {
            "session": session,
            "professor": professor["professor"]
        }
        
        if day_of_week == 5:  # Saturday
            saturday_sessions.append(session_data)
        elif day_of_week == 6:  # Sunday
            sunday_sessions.append(session_data)
        else:
            other_sessions.append(session_data)
    
    html = f"""
    <div style="margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
        <div class="mb-4 p-4 bg-green-50 rounded-lg">
            <p><strong>To:</strong> {admin_email} (for forwarding to {cohort_name} learners)</p>
            <p><strong>Subject:</strong> Reminder: Upcoming Live Sessions This Weekend - {cohort_name}</p>
            <p><strong>Type:</strong> <span class="text-green-600 font-semibold">Learner Email</span></p>
        </div>
        <div class="email-preview">
            <p>Dear Learner,</p>
            <p>Greetings from upGrad!</p>
            <p>We hope this message finds you in good health and high spirits. We are writing to remind you about the upcoming live sessions scheduled for this weekend.</p>
    """
    
    # Add Saturday sessions
    html += "<p><strong>Sessions on Saturday:</strong></p>"
    if saturday_sessions:
        for session_data in saturday_sessions:
            session = session_data["session"]
            professor_name = session_data["professor"]
            session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
            
            html += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #3b82f6; background-color: #f8fafc;">
                <p><strong>Date:</strong> {session_date}</p>
                <p><strong>Time:</strong> {session['time']}</p>
                <p><strong>Topic:</strong> {session['topic']}</p>
                <p><strong>Conducted by:</strong> {professor_name}</p>
                <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #3b82f6; text-decoration: underline;">{session['link']}</a></p>
            </div>
            """
    else:
        html += """
        <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
            <p style="color: #d97706; font-weight: bold;">No Live sessions scheduled on Saturday</p>
        </div>
        """
    
    # Add Sunday sessions
    html += "<p><strong>Sessions on Sunday:</strong></p>"
    if sunday_sessions:
        for session_data in sunday_sessions:
            session = session_data["session"]
            professor_name = session_data["professor"]
            session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
            
            html += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #10b981; background-color: #f0fdf4;">
                <p><strong>Date:</strong> {session_date}</p>
                <p><strong>Time:</strong> {session['time']}</p>
                <p><strong>Topic:</strong> {session['topic']}</p>
                <p><strong>Conducted by:</strong> {professor_name}</p>
                <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #10b981; text-decoration: underline;">{session['link']}</a></p>
            </div>
            """
    else:
        html += """
        <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
            <p style="color: #d97706; font-weight: bold;">No Live sessions scheduled on Sunday</p>
        </div>
        """
    
    # Add other day sessions if any
    if other_sessions:
        html += "<p><strong>Other Sessions (Weekdays):</strong></p>"
        for session_data in other_sessions:
            session = session_data["session"]
            professor_name = session_data["professor"]
            session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%b %d, %Y, %A")
            
            html += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #f59e0b; background-color: #fffbeb;">
                <p><strong>Date:</strong> {session_date}</p>
                <p><strong>Time:</strong> {session['time']}</p>
                <p><strong>Topic:</strong> {session['topic']}</p>
                <p><strong>Conducted by:</strong> {professor_name}</p>
                <p><strong>Join Zoom Meeting:</strong> <a href="{session['link']}" style="color: #f59e0b; text-decoration: underline;">{session['link']}</a></p>
            </div>
            """
    
    html += """
            <div style="margin-top: 30px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f1f5f9;">
                <p><strong>Time Zone Converter:</strong></p>
                <p>Below is the link for World Time Buddy. You can set the time according to your local time zone:</p>
                <p><a href="https://www.worldtimebuddy.com/" style="color: #3b82f6; text-decoration: underline;">https://www.worldtimebuddy.com/</a></p>
            </div>
            
            <p style="margin-top: 20px;"><strong>Best regards,</strong><br>
            <strong>upGrad Team</strong></p>
        </div>
    </div>
    """
    return html
