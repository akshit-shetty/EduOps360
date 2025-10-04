# app.py
from flask import Flask, jsonify, request, send_file,render_template, Blueprint
from flask_cors import CORS
import win32com.client as win32
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
import pythoncom
import tempfile


reminders_bp = Blueprint("reminder", __name__)
CORS(reminders_bp)


@reminders_bp.route("/")
def reminder_home():
    return render_template("reminder.html")

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

                session = {
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "time": row["ProfessorTime"],
                    "topic": row["Topic"],
                    "link": row["Session_Link"],
                    "drive": drive_link
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
def send_emails(preview_only=False):
    global email_status, sessions_data
    
    pythoncom.CoInitialize()  # Initialize COM for this thread
    
    try:
        outlook = win32.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        from_address = "ggugenai.operations@upgrad.com"
        
        # Find the correct account
        account = None
        for acc in namespace.Accounts:
            if acc.SmtpAddress.lower() == from_address.lower():
                account = acc
                break
        
        if not account:
            raise Exception(f"Account {from_address} not found in Outlook profiles")
        
        # Create preview folder if needed
        preview_folder = "Email_Previews"
        if preview_only and not os.path.exists(preview_folder):
            os.makedirs(preview_folder)
        
        # Process each professor
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
            
            # Subject
            subject = f"Reminder: Upcoming Live Sessions This Weekend for {prof_name}"
            
            # HTML Email body
            body = f"""
            <p>Hello <b>{prof_name}</b>,</p>
            <p>I hope this message finds you well. This is a gentle reminder regarding your upcoming sessions scheduled for this weekend.</p>
            <p><b>Session Details:</b></p>
            <ul>
            """
            
            for session in professor["sessions"]:
                session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%B %d, %Y, %A")
                body += f"""
                <li>
                    <b>Date:</b> {session_date}<br>
                    <b>Time:</b> {session['time']}<br>
                    <b>Topic:</b> {session['topic']}<br>
                    <b>Zoom:</b> <a href="{session['link']}">Join Meeting</a><br>
                """
                
                drive_link = session["drive"]
                print(f"DEBUG: Drive link for {prof_name}: '{drive_link}' (type: {type(drive_link)})")
                
                if drive_link and isinstance(drive_link, str) and drive_link.strip() and not drive_link.isspace():
                    print(f"DEBUG: Adding drive link: {drive_link}")
                    body += f'<b>Drive Link:</b> <a href="{drive_link}">Upload PPTs/Materials</a><br><br>'
                else:
                    print(f"DEBUG: No valid drive link found, showing default message")
                    body += "Kindly share the PPTs or materials that need to be shared with the learners in this email.<br><br>"             
                body += "</li>"
            
            body += """
            </ul>
            <p>Please let us know if you require any assistance or have any updates regarding the session. 
            We look forward to a successful weekend of learning!</p>
            <p>Best regards,<br>Operations Team</p>
            """
            
            # Create mail
            mail = outlook.CreateItem(0)
            mail.To = email
            mail.CC = "akshit1.shetty@upgrad.com"
            mail.Subject = subject
            mail.HTMLBody = body
            mail._oleobj_.Invoke(*(64209, 0, 8, 0, account))  # Force sending from this account
            
            if preview_only:
                # Save as draft file (.msg) instead of sending
                preview_path = os.path.join(preview_folder, f"{prof_name}_{email}.msg".replace(" ", "_"))
                mail.SaveAs(preview_path)
                email_status[email] = {
                    "professor": prof_name,
                    "status": "preview",
                    "message": f"Preview saved: {preview_path}"
                }
            else:
                try:
                    mail.Send()
                    email_status[email] = {
                        "professor": prof_name,
                        "status": "sent",
                        "message": "Email sent successfully"
                    }
                except Exception as e:
                    email_status[email] = {
                        "professor": prof_name,
                        "status": "error",
                        "message": f"Failed to send email: {str(e)}"
                    }
    
    except Exception as e:
        print(f"Error in email sending: {e}")
    finally:
        pythoncom.CoUninitialize()  # Uninitialize COM

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
    global uploaded_file_path
    
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
        # Save the uploaded file temporarily
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        uploaded_file_path = file_path
        
        # Load sessions from the uploaded file
        sessions = load_sessions_from_excel(file_path)
        
        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "message": f"Successfully loaded {len(sessions)} professors"
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
    return jsonify(email_status)

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
    
    if not sessions_data:
        return jsonify({
            "success": False,
            "error": "No sessions loaded. Please upload an Excel file first."
        }), 400
    
    send_emails(preview_only=preview_only)
    
    return jsonify({
        "success": True,
        "message": "Email sending process started"
    })

@reminders_bp.route('/api/reset', methods=['POST'])
def reset_data():
    global email_status, sessions_data, uploaded_file_path
    email_status = {}
    sessions_data = []
    uploaded_file_path = None
    
    return jsonify({
        "success": True,
        "message": "Data reset successfully"
    })

@reminders_bp.route('/api/preview-email/<email>', methods=['GET'])
def preview_email(email):
    # Find the professor with this email
    professor = next((p for p in sessions_data if p["email"] == email), None)
    
    if not professor:
        return jsonify({
            "success": False,
            "error": "Professor not found"
        }), 404
    
    prof_name = professor["professor"]
    
    # Generate HTML preview
    html = f"""
    <div style="margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
        <p><strong>To:</strong> {prof_name} &lt;{email}&gt;</p>
        <p><strong>Subject:</strong> Reminder: Upcoming Live Sessions This Weekend for {prof_name}</p>
        <div class="email-preview">
            <p>Hello <b>{prof_name}</b>,</p>
            <p>I hope this message finds you well. This is a gentle reminder regarding your upcoming sessions scheduled for this weekend.</p>
            <p><b>Session Details:</b></p>
            <ul>
    """
    
    for session in professor["sessions"]:
        session_date = datetime.strptime(session["date"], "%Y-%m-%d").strftime("%B %d, %Y, %A")
        html += f"""
            <li>
                <b>Date:</b> {session_date}<br>
                <b>Time:</b> {session['time']}<br>
                <b>Topic:</b> {session['topic']}<br>
                <b>Zoom:</b> <a href="{session['link']}">Join Meeting</a><br>
        """
        

        drive_link = session["drive"]
        if drive_link and isinstance(drive_link, str) and drive_link.strip() and not drive_link.isspace():
            html += f'<b>Drive Link:</b> <a href="{drive_link}">Upload PPTs/Materials</a><br><br>'
        else:
            html += "Kindly share the PPTs or materials that need to be shared with the learners in this email.<br><br>"   
        html += "</li>"
    
    html += """
            </ul>
            <p>Please let us know if you require any assistance or have any updates regarding the session. 
            We look forward to a successful weekend of learning!</p>
            <p>Best regards,<br>Operations Team</p>
        </div>
    </div>
    """
    
    return jsonify({
        "success": True,
        "preview": html
    })
