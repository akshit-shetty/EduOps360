from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pandas as pd
import os
from datetime import datetime, timedelta
from functools import wraps
import secrets
import subprocess
import sys
import traceback
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from auth.otp_auth import OTPAuthenticator, send_login_otp, verify_login_otp, get_user_by_email
from auth.email_config import get_email_accounts
from utils.coursework_analytics import get_coursework_dashboard_stats, get_live_session_analytics, get_coursework_overview
from routes.chatbot import chatbot_bp
from routes.reminder import reminders_bp
from routes.email_campaigns import campaigns_bp
from utils.ratings_utils import convert_ratings_to_numeric
from utils.database import get_db_connection, get_db_cursor, execute_query, execute_many
from config.config import Config

# Load environment variables
load_dotenv()

print("Python version:", sys.version)
app = Flask(__name__)
# Secure configuration from environment variables
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_urlsafe(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=int(os.getenv('SESSION_TIMEOUT_HOURS', 24)))
# Constants - Database configuration now handled in Config class

LOW_GRADES = ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I']
COURSE_COLUMNS = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                 'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
ACTIVE_STATUSES = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']

# Register blueprints
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
app.register_blueprint(reminders_bp, url_prefix='/reminder')
app.register_blueprint(campaigns_bp, url_prefix='/campaigns')

# Authentication functions (OTP-based)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Fixed: session instead of session
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Removed duplicate admin_users function - using the more complete one below

@app.route('/admin/add-user', methods=['POST'])
@admin_required
def admin_add_user():
    """Add new user from admin panel"""
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'user').strip()
    password = request.form.get('password', '').strip()
    
    # Validate inputs
    if not all([first_name, last_name, email, role]):
        flash('All fields are required', 'error')
        return redirect(url_for('admin_users'))
    
    if not password:
        # Generate random password if not provided
        password = secrets.token_urlsafe(12)
    
    # Hash password
    password_hash = hash_password(password)
    
    try:
        with get_db_cursor() as cursor:
            # Check if user already exists
            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Update existing user
                cursor.execute('''
                    UPDATE users 
                    SET first_name = %s, last_name = %s, password_hash = %s, role = %s, is_active = TRUE
                    WHERE email = %s
                ''', (first_name, last_name, password_hash, role, email))
                flash(f'User {email} updated successfully!', 'success')
            else:
                # Create new user
                cursor.execute('''
                    INSERT INTO users (first_name, last_name, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (first_name, last_name, email, password_hash, role))
                flash(f'User {email} created successfully! Password: {password}', 'success')
        
    except Exception as e:
        print(f"Error adding user: {e}")
        flash(f'Error creating user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    """Toggle user active status"""
    conn = get_db_connection()
    if not conn:
        flash('Error connecting to database', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            new_status = not bool(user[0])
            cursor.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
            conn.commit()
            
            status_text = 'activated' if new_status else 'deactivated'
            flash(f'User {status_text} successfully!', 'success')
        else:
            flash('User not found', 'error')
            
    except Exception as e:
        print(f"Error toggling user status: {e}")
        flash('Error updating user status', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_users'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Delete a user"""
    # Prevent users from deleting themselves
    if user_id == session.get('user_id'):
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    if not conn:
        flash('Error connecting to database', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash('User deleted successfully!', 'success')
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        flash('Error deleting user', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_users'))

@app.route('/admin/test-upload', methods=['GET'])
@admin_required
def test_upload():
    """Test endpoint to verify server is responding"""
    return jsonify({'success': True, 'message': 'Server is responding correctly'})

@app.route('/admin/upload-database', methods=['POST'])
@admin_required
def admin_upload_database():
    """Handle Excel file upload and convert to database using db.py"""
    temp_path = None
    try:
        if 'database_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'})
        
        file = request.files['database_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload an Excel file (.xlsx or .xls)'})
        
        # Save uploaded file temporarily with unique name and better error handling
        import tempfile
        import time
        import uuid
        
        # Create a unique temporary file
        temp_dir = tempfile.gettempdir()
        filename = secure_filename(file.filename)
        base_name, ext = os.path.splitext(filename)
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{base_name}_{unique_id}_{int(time.time())}{ext}"
        temp_path = os.path.join(temp_dir, unique_filename)
        
        # Save file with proper error handling
        try:
            file.save(temp_path)
            # Verify file was saved correctly
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                return jsonify({'success': False, 'message': 'File upload failed. Please try again.'})
        except Exception as save_error:
            print(f"File save error: {save_error}")
            return jsonify({'success': False, 'message': 'Failed to save uploaded file. Please try again.'})
        
        try:
            # Import and use the db.py function with better error handling
            import importlib.util
            import sys
            
            db_script_path = os.path.join(os.path.dirname(__file__), 'db_postgresql.py')
            
            if not os.path.exists(db_script_path):
                return jsonify({'success': False, 'message': 'Processing script not found'})
            
            # Import db module with error handling
            try:
                spec = importlib.util.spec_from_file_location("db_module", db_script_path)
                db_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(db_module)
            except Exception as import_error:
                print(f"❌ Import error: {import_error}")
                return jsonify({'success': False, 'message': 'Error loading processing module'})
            
            # Call the excel_to_postgresql function
            print(f"Processing Excel file: {unique_filename}")
            print(f"Target database: PostgreSQL")
            
            try:
                success = db_module.excel_to_postgresql(temp_path)
                
                if success:
                    print(f"✅ Database updated successfully from: {unique_filename}")
                    response_data = {'success': True, 'message': 'Database updated successfully! Your Excel file has been processed and all data has been imported.'}
                    print(f"Returning success response: {response_data}")
                    return jsonify(response_data)
                else:
                    print(f"❌ Failed to process Excel file: {unique_filename}")
                    response_data = {'success': False, 'message': 'Error processing file. Please check the Excel file format and try again.'}
                    print(f"Returning error response: {response_data}")
                    return jsonify(response_data)
                    
            except Exception as processing_error:
                print(f"❌ Processing error: {processing_error}")
                return jsonify({'success': False, 'message': f'Database processing failed: {str(processing_error)}'})
                
        except Exception as e:
            print(f"❌ Excel processing error: {e}")
            return jsonify({'success': False, 'message': f'Processing failed: {str(e)}'})
            
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'message': f'Upload error: {str(e)}'})
    
    finally:
        # Clean up temporary file with improved retry mechanism
        if temp_path and os.path.exists(temp_path):
            def cleanup_temp_file(file_path, max_retries=5):
                import time
                for attempt in range(max_retries):
                    try:
                        # Wait for any file handles to close
                        time.sleep(0.1 * (attempt + 1))
                        os.remove(file_path)
                        print(f"🗑️ Cleaned up temporary file: {file_path}")
                        return True
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"⚠️ Could not clean up temp file after {max_retries} attempts: {e}")
                            # Schedule for later cleanup
                            try:
                                import atexit
                                atexit.register(lambda: os.remove(file_path) if os.path.exists(file_path) else None)
                                print(f"📅 Scheduled temp file for cleanup on exit: {file_path}")
                            except:
                                pass
                            return False
                        else:
                            print(f"🔄 Cleanup attempt {attempt + 1} failed, retrying...")
                            continue
                return False
            
            cleanup_temp_file(temp_path)

def get_last_updated_time():
    """Get the last updated time from database metadata"""
    try:
        # For PostgreSQL, we can query system tables or use a metadata table
        # For now, return current time as placeholder
        return datetime.now()
    except:
        pass
    return datetime.now()

def get_data_last_updated():
    """Get the last updated time for data (alias for get_last_updated_time)"""
    return get_last_updated_time()
def apply_filters(df, cohort_filter=None, slot_filter=None, status_filter=None, country_filter=None):
    """Apply filters to dataframe - now handles multiple values"""
    print(f"🔍 APPLY_FILTERS: Input filters - cohort: {cohort_filter}, slot: {slot_filter}, status: {status_filter}")
    
    if cohort_filter and len(cohort_filter) > 0:
        # Handle both single value and list of values
        if not isinstance(cohort_filter, list):
            cohort_filter = [cohort_filter]
        # Convert cohort values to the same type as in the dataframe
        try:
            # Try to convert to integer if possible
            cohort_filter = [int(cohort) for cohort in cohort_filter if cohort]
            df = df[df['Cohort #'].isin(cohort_filter)]
        except (ValueError, TypeError):
            # If conversion fails, use as string
            cohort_filter = [str(cohort) for cohort in cohort_filter if cohort]
            df = df[df['Cohort #'].astype(str).isin(cohort_filter)]
    
    if slot_filter and len(slot_filter) > 0:
        if not isinstance(slot_filter, list):
            slot_filter = [slot_filter]
        # Handle slot filtering (first 6 characters)
        slot_filter = [slot[:6] for slot in slot_filter if slot]
        df = df[df['Slot'].str[:6].isin(slot_filter)]
    
    if status_filter and len(status_filter) > 0:
        if not isinstance(status_filter, list):
            status_filter = [status_filter]
        df = df[df['Status'].isin(status_filter)]
    
    if country_filter:
        if not isinstance(country_filter, list):
            country_filter = [country_filter]
        # Filter by Country of Residence
        df = df[df['Country of Residence'].isin(country_filter)]
    
    return df


def get_learners_with_low_grades(gradesheet_df):
    """Identify learners with low grades"""
    active_learners = gradesheet_df[gradesheet_df['Status'].isin(ACTIVE_STATUSES)]
    learners_with_low_grades = []
    
    for _, row in active_learners.iterrows():
        low_grade_courses = []
        formatted_courses = []
        
        for course in COURSE_COLUMNS:
            if row[course] in LOW_GRADES:
                course_name = course.replace(' Grade', '')
                credit_column = course.replace('Grade', 'Credit')
                credit_value = row.get(credit_column, 'N/A')
                
                low_grade_courses.append(course_name)
                formatted_courses.append(f"{course_name}: {row[course]}, {credit_value}")
        
        if low_grade_courses:
            learners_with_low_grades.append({
                'Name': f"{row['First Name']} {row['Last Name']}",
                'User_ID': row['User ID'],  # Added User ID field for profile linking
                'Email': row['Email'],  # Keep Email for reference
                'Cohort': row['Cohort #'],
                'Slot': str(row['Slot'])[:6] if pd.notna(row['Slot']) else 'N/A',
                'Status': row['Status'],
                'Courses with Low Grades': ', '.join(low_grade_courses),
                'FormattedCourses': '; '.join(formatted_courses),
                'Number of Courses': len(low_grade_courses),
            })
    
    return learners_with_low_grades

def get_dashboard_data(cohort_filter=None, slot_filter=None, status_filter=None, search_filter=None, page=1, per_page=5):
    """Get data for dashboard with pagination"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Read data from the tables
        gradesheet_df = pd.read_sql_query("SELECT * FROM Gradesheet", conn)
        student_list_df = pd.read_sql_query("SELECT * FROM \"Student List\"", conn)
        
        # Apply filters to both dataframes for consistency
        filtered_student_list = apply_filters(student_list_df, cohort_filter, slot_filter, status_filter)
        
        # Count unique learners (by email)
        total_learners = len(filtered_student_list['Email'].dropna().unique())
        
        # Count International vs Domestic
        international_emails = filtered_student_list[
            filtered_student_list['Batch'].str.contains('International', na=False)
        ]['Email'].dropna().unique()
        domestic_emails = filtered_student_list[
            ~filtered_student_list['Batch'].str.contains('International', na=False)
        ]['Email'].dropna().unique()
        
        international_count = len(international_emails)
        domestic_count = len(domestic_emails)
        
        # Calculate average CGPA
        filtered_emails = filtered_student_list['Email'].dropna().unique().tolist()
        filtered_gradesheet = gradesheet_df[gradesheet_df['Email'].isin(filtered_emails)]
        avg_cgpa = filtered_gradesheet['Overall CGPA'].mean()
        
        # Identify learners with low grades
        learners_with_low_grades = get_learners_with_low_grades(filtered_gradesheet)
        
        # Apply search filter if provided
        if search_filter:
            search_filter = search_filter.lower()
            learners_with_low_grades = [
                learner for learner in learners_with_low_grades
                if search_filter in learner['Name'].lower()
                or search_filter in str(learner['Cohort']).lower()
                or search_filter in str(learner['Slot']).lower()
                or search_filter in learner['Status'].lower()
            ]
        
        low_credit_count = len(learners_with_low_grades)
        
        # ADD DISSERTATION PHASE CALCULATION (Same logic as in get_all_learners_data)
        # Use the same logic as in get_all_learners_data
        merged_for_count = filtered_student_list.merge(
            gradesheet_df[['Email', 'Cohort #', 'Courses Completed', 'Courses Incomplete']],
            on=['Email', 'Cohort #'],
            how='left'
        )

        # Remove any potential duplicates from the merge
        merged_for_count = merged_for_count.drop_duplicates(subset=['Email', 'Cohort #', 'First Name', 'Last Name'])

        merged_for_count['Courses Completed'] = merged_for_count['Courses Completed'].fillna(0).astype(int)
        merged_for_count['Courses Incomplete'] = merged_for_count['Courses Incomplete'].fillna(0).astype(int)
        merged_for_count['Net Completed'] = merged_for_count['Courses Completed'] - merged_for_count['Courses Incomplete']

        # Count learners who have completed all 7 courses (Net Completed = 7)
        # Or use >= 6 if you want to include those close to completion
        completed_learners_count = len(merged_for_count[merged_for_count['Net Completed'] == 7])
        
        print(f"Dissertation phase learners (Net Completed = 7): {completed_learners_count}")

        # Build filter lists from full dataset
        cohorts = sorted(student_list_df['Cohort #'].dropna().unique())
        slots = sorted(student_list_df['Slot'].dropna().str.slice(0, 6).unique())
        statuses = sorted(student_list_df['Status'].dropna().unique())
        
        # Pagination
        total_pages = (low_credit_count + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_low_credit = learners_with_low_grades[start_idx:end_idx]
        
        return {
            'total_learners': total_learners,
            'international_count': international_count,
            'domestic_count': domestic_count,
            'avg_cgpa': avg_cgpa if not pd.isna(avg_cgpa) else 0,
            'low_credit_count': low_credit_count,
            'completed_learners_count': completed_learners_count,  # Now this will be defined
            'learners_with_low_grades': paginated_low_credit,
            'cohorts': cohorts,
            'slots': slots,
            'statuses': statuses,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_low_credit': low_credit_count,
                'pages': total_pages,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1,
                'next_num': page + 1
            }
        }
        
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return None
    finally:
        conn.close()

def get_dissertation_analytics(cohort_filter=None, total_dissertation_students=None):
    """Get detailed dissertation milestone analytics with status breakdown"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Check if Dissertation table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Dissertation'")
        if not cursor.fetchone():
            print("Dissertation table does not exist")
            return get_default_dissertation_data()
        
        print("Dissertation table found, proceeding with analytics...")
        
        # First check what columns exist in Dissertation table
        cursor.execute("PRAGMA table_info(Dissertation)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Available columns in Dissertation table: {columns}")
        
        # Get all dissertation data (no Student List join for milestones)
        # Build dissertation query with optional cohort filter
        if cohort_filter:
            dissertation_query = '''
            SELECT DISTINCT d."Email", d."Topic Proposal Submission", d."Topic Proposal Approval",
                   d."IRB", d."Research Proposal Submission", d."Research Proposal Approval",
                   d."Final Proposal Submission", d."Final Proposal Approval"
            FROM "Dissertation" d
            LEFT JOIN "Student List" s ON d."Email" = s."Email"
            WHERE s."Cohort #" = ?
            '''
            dissertation_df = pd.read_sql_query(dissertation_query, conn, params=[cohort_filter])
        else:
            dissertation_query = '''
            SELECT "Email", "Topic Proposal Submission", "Topic Proposal Approval",
                   "IRB", "Research Proposal Submission", "Research Proposal Approval",
                   "Final Proposal Submission", "Final Proposal Approval"
            FROM "Dissertation"
            '''
            dissertation_df = pd.read_sql_query(dissertation_query, conn)
        
        if dissertation_df.empty:
            print("No dissertation students found")
            return get_default_dissertation_data()
        
        print(f"Total dissertation records: {len(dissertation_df)}")
        
        # Filter dissertation students to only those with 7 completed courses using Gradesheet
        gradesheet_query = '''
        SELECT "Email", "Cohort #", "Courses Completed", "Courses Incomplete"
        FROM "Gradesheet"
        '''
        
        gradesheet_df = pd.read_sql_query(gradesheet_query, conn)
        gradesheet_df['Net Completed'] = gradesheet_df['Courses Completed'] - gradesheet_df['Courses Incomplete']
        
        # Get emails of students with 7 completed courses
        students_with_7_courses = gradesheet_df[gradesheet_df['Net Completed'] == 7]
        
        # Apply cohort filter if specified
        if cohort_filter:
            students_with_7_courses = students_with_7_courses[students_with_7_courses['Cohort #'] == cohort_filter]
        
        eligible_emails = students_with_7_courses['Email'].tolist()
        print(f"Students with 7 completed courses: {len(eligible_emails)}")
        
        # Filter dissertation data by active status for milestone calculations
        # Use ALL dissertation data for milestone calculations (no status filtering)
        filtered_dissertation_df = dissertation_df
        
        print(f"Using all {len(filtered_dissertation_df)} dissertation records for milestone calculations")
        
        # Use the passed total_dissertation_students count from dashboard data
        if total_dissertation_students is not None:
            total = total_dissertation_students
            print(f"Using passed dissertation phase count: {total}")
        else:
            # Fallback: use active dissertation count
            total = len(filtered_dissertation_df)
            print(f"Using active dissertation count as fallback: {total}")
        
        print(f"Using {len(filtered_dissertation_df)} dissertation records (7 courses) for milestone data with total count of {total}")
        
        # Topic Proposal Status Breakdown (using both submission and approval columns)
        topic_proposal_stats = get_milestone_breakdown(filtered_dissertation_df, 'Topic Proposal Submission', 'Topic Proposal Approval', total)
        
        # IRB Status Breakdown (IRB column contains submission status)
        irb_stats = get_milestone_breakdown(filtered_dissertation_df, 'IRB', None, total)
        
        # Research Proposal Status Breakdown
        research_proposal_stats = get_milestone_breakdown(filtered_dissertation_df, 'Research Proposal Submission', 'Research Proposal Approval', total)
        
        # Final Defense Status Breakdown
        final_defense_stats = get_milestone_breakdown(filtered_dissertation_df, 'Final Proposal Submission', 'Final Proposal Approval', total)
        
        # Calculate overall pending review (total submitted - total approved - total not approved)
        total_submitted = (topic_proposal_stats['submitted']['count'] + 
                          irb_stats['submitted']['count'] + 
                          research_proposal_stats['submitted']['count'] + 
                          final_defense_stats['submitted']['count'])
        
        total_approved = (topic_proposal_stats['approved']['count'] + 
                         irb_stats['approved']['count'] + 
                         research_proposal_stats['approved']['count'] + 
                         final_defense_stats['approved']['count'])
        
        total_not_approved = (topic_proposal_stats['not_approved']['count'] + 
                             irb_stats['not_approved']['count'] + 
                             research_proposal_stats['not_approved']['count'] + 
                             final_defense_stats['not_approved']['count'])
        
        overall_pending_review = max(0, total_submitted - total_approved - total_not_approved)
        
        return {
            'total_dissertation': total,
            'topic_proposal': topic_proposal_stats,
            'irb': irb_stats,
            'research_proposal': research_proposal_stats,
            'final_defense': final_defense_stats,
            'overall_pending_review': overall_pending_review,
            'total_approvals': total_approved,
            'total_not_approved': total_not_approved
        }
        
    except Exception as e:
        print(f"Error getting dissertation analytics: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return get_default_dissertation_data()
    finally:
        conn.close()

def get_default_dissertation_data():
    """Return default dissertation data structure"""
    return {
        'total_dissertation': 0,
        'topic_proposal': {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        },
        'irb': {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        },
        'research_proposal': {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        },
        'final_defense': {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        },
        'overall_pending_review': 0,
        'total_approvals': 0,
        'total_not_started': 0
    }

def get_milestone_breakdown(df, submission_column, approval_column, total):
    """Get milestone breakdown using separate submission and approval columns"""
    
    # Initialize counts
    submitted = 0
    approved = 0
    not_approved = 0
    not_submitted = 0
    
    print(f"Processing milestone: submission='{submission_column}', approval='{approval_column}', total={total}")
    
    # Count submissions (only actual 'Submitted' values, not '0' or NULL)
    if submission_column and submission_column in df.columns:
        submitted = len(df[df[submission_column] == 'Submitted'])
        print(f"  Submitted count: {submitted}")
        # Debug: show unique values
        unique_vals = df[submission_column].value_counts(dropna=False)
        print(f"  Unique values in {submission_column}: {dict(unique_vals)}")
    elif submission_column:
        print(f"  Warning: Submission column '{submission_column}' not found")
    
    # Count approvals from approval column
    if approval_column and approval_column in df.columns:
        approved = len(df[df[approval_column] == 'Approved'])
        not_approved = len(df[df[approval_column] == 'Not Approved'])
        print(f"  Approved count: {approved}, Not approved count: {not_approved}")
        # Debug: show unique values
        unique_vals = df[approval_column].value_counts(dropna=False)
        print(f"  Unique values in {approval_column}: {dict(unique_vals)}")
    elif approval_column:
        print(f"  Warning: Approval column '{approval_column}' not found")
    
    # Not submitted = Total - Submitted (students who haven't reached this milestone yet)
    # Count explicit "Not Submitted" values (including typo "Not Submited")
    if submission_column and submission_column in df.columns:
        not_submitted_mask = (
            (df[submission_column] == 'Not Submitted') |
            (df[submission_column] == 'Not Submited')  # Handle typo
        )
        not_submitted = len(df[not_submitted_mask])
        print(f"  Explicit Not Submitted count: {not_submitted}")
    else:
        not_submitted = 0  # If no submission column, no explicit "Not Submitted" values
    
    return {
        'submitted': {
            'count': submitted,
            'percent': round((submitted / (submitted + not_submitted) * 100) if (submitted + not_submitted) > 0 else 0)
        },
        'not_submitted': {
            'count': not_submitted,
            'percent': round((not_submitted / (submitted + not_submitted) * 100) if (submitted + not_submitted) > 0 else 0)
        },
        'approved': {
            'count': approved,
            'percent': round((approved / (approved + not_approved) * 100) if (approved + not_approved) > 0 else 0)
        },
        'not_approved': {
            'count': not_approved,
            'percent': round((not_approved / (approved + not_approved) * 100) if (approved + not_approved) > 0 else 0)
        }
    }

def get_status_breakdown(df, column_name, total):
    """Legacy function - kept for compatibility"""
    return get_milestone_breakdown(df, None, column_name, total)

def get_irb_breakdown(df, total):
    """Get IRB status breakdown (special handling)"""
    if 'IRB' not in df.columns:
        return {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        }
    
    # Count different IRB statuses
    approved = len(df[df['IRB'] == 'Approved'])
    not_approved = len(df[df['IRB'] == 'Not Approved'])
    submitted = len(df[df['IRB'] == 'Submitted'])
    
    # Count only explicit "Not Submitted" values (including typo "Not Submited")
    not_submitted = len(df[(df['IRB'] == 'Not Submitted') | 
                          (df['IRB'] == 'Not Submited')])
    
    return {
        'submitted': {
            'count': submitted,
            'percent': round((submitted / total * 100) if total > 0 else 0)
        },
        'not_submitted': {
            'count': not_submitted,
            'percent': round((not_submitted / total * 100) if total > 0 else 0)
        },
        'approved': {
            'count': approved,
            'percent': round((approved / total * 100) if total > 0 else 0)
        },
        'not_approved': {
            'count': not_approved,
            'percent': round((not_approved / total * 100) if total > 0 else 0)
        }
    }

# In the get_all_learners_data function, remove country_filter parameter and usage

def get_learner_statistics():
    """Calculate learner statistics for the learners page cards"""
    conn = get_db_connection()
    if not conn:
        return {
            'total_learners': 0,
            'active_learners': 0,
            'failed_dropout': 0,
            'completed_learners': 0,
            'inactive_learners': 0
        }
    
    try:
        # Get all students from Student List table
        student_df = pd.read_sql_query('SELECT * FROM "Student List"', conn)
        print(f"🔍 STATISTICS: Student List table has {len(student_df)} rows")
        
        # Get dissertation data to check for completed milestones
        dissertation_df = pd.read_sql_query('SELECT * FROM "Dissertation"', conn)
        print(f"🔍 STATISTICS: Dissertation table has {len(dissertation_df)} rows")
        
        # 1. Total unique learners from Student List table
        total_learners = len(student_df.drop_duplicates(subset=['Email']))
        
        # 2. Active learners (Status: Active and Active / Deferred In)
        active_statuses = ['Active', 'Active / Deferred In']
        active_learners = len(student_df[student_df['Status'].isin(active_statuses)].drop_duplicates(subset=['Email']))
        
        # 3. Failed / Drop Out learners (Status: Drop Out, Self Pace, In Process of Program Change, Program Changed)
        failed_statuses = ['Drop Out', 'Self Pace', 'In Process of Program Change', 'Program Changed']
        failed_dropout = len(student_df[student_df['Status'].isin(failed_statuses)].drop_duplicates(subset=['Email']))
        
        # 4. Completed learners (completed all 4 milestones with Approved)
        # Check for students who have all 4 milestones approved
        completed_learners = 0
        if not dissertation_df.empty:
            # Count students with all 4 milestones approved
            milestone_columns = ['Topic Proposal Approval', 'IRB', 'Research Proposal Approval', 'Final Proposal Approval']
            
            # For each student, check if all milestones are approved
            for _, row in dissertation_df.iterrows():
                approved_count = 0
                if row.get('Topic Proposal Approval') == 'Approved':
                    approved_count += 1
                if row.get('IRB') == 'Approved':  # IRB might be approval status
                    approved_count += 1
                if row.get('Research Proposal Approval') == 'Approved':
                    approved_count += 1
                if row.get('Final Proposal Approval') == 'Approved':
                    approved_count += 1
                
                if approved_count == 4:
                    completed_learners += 1
        
        # 5. Inactive learners (Status: In Process of Deferral)
        inactive_statuses = ['In Process of Deferral']
        inactive_learners = len(student_df[student_df['Status'].isin(inactive_statuses)].drop_duplicates(subset=['Email']))
        
        return {
            'total_learners': total_learners,
            'active_learners': active_learners,
            'failed_dropout': failed_dropout,
            'completed_learners': completed_learners,
            'inactive_learners': inactive_learners
        }
        
    except Exception as e:
        print(f"Error calculating learner statistics: {e}")
        return {
            'total_learners': 0,
            'active_learners': 0,
            'failed_dropout': 0,
            'completed_learners': 0,
            'inactive_learners': 0
        }
    finally:
        conn.close()

def get_all_learners_data(cohort_filter=None, slot_filter=None, status_filter=None, search_filter=None, page=1, per_page=10):
    """Get data for all learners page - OPTIMIZED for performance"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Optimized: Use SQL WHERE clauses to filter data at database level
        base_query = "SELECT * FROM \"Student List\""
        where_conditions = []
        params = []
        
        # Apply filters at SQL level for better performance
        if status_filter and len(status_filter) > 0:
            placeholders = ','.join(['?' for _ in status_filter])
            where_conditions.append(f"Status IN ({placeholders})")
            params.extend(status_filter)
        
        if cohort_filter and len(cohort_filter) > 0:
            try:
                cohort_filter_int = [int(c) for c in cohort_filter if c]
                placeholders = ','.join(['?' for _ in cohort_filter_int])
                where_conditions.append(f"\"Cohort #\" IN ({placeholders})")
                params.extend(cohort_filter_int)
            except (ValueError, TypeError):
                cohort_filter_str = [str(c) for c in cohort_filter if c]
                placeholders = ','.join(['?' for _ in cohort_filter_str])
                where_conditions.append(f"\"Cohort #\" IN ({placeholders})")
                params.extend(cohort_filter_str)
        
        if slot_filter and len(slot_filter) > 0:
            # Use LIKE for slot filtering since we only match first 6 characters
            slot_conditions = []
            for slot in slot_filter:
                if slot:
                    slot_conditions.append("Slot LIKE ?")
                    params.append(f"{slot[:6]}%")
            if slot_conditions:
                where_conditions.append(f"({' OR '.join(slot_conditions)})")
        
        # Build final query
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        print(f"🔍 OPTIMIZED QUERY: {base_query}")
        student_list_df = pd.read_sql_query(base_query, conn, params=params)
        print(f"🔍 LEARNERS DATA: Filtered Student List has {len(student_list_df)} rows")
        
        # Use the already filtered data as working dataset
        working_df = student_list_df.copy()
        
        # Apply search filter efficiently
        if search_filter:
            search_filter = search_filter.lower()
            # Optimized search with fewer string operations
            mask = (
                working_df['First Name'].str.lower().str.contains(search_filter, na=False) |
                working_df['Last Name'].str.lower().str.contains(search_filter, na=False) |
                working_df['Email'].str.lower().str.contains(search_filter, na=False) |
                working_df['Cohort #'].astype(str).str.contains(search_filter, na=False) |
                working_df['User ID'].astype(str).str.contains(search_filter, na=False)
            )
            working_df = working_df[mask]
            print(f"🔍 LEARNERS DATA: After search - {len(working_df)} rows remaining")
        
        # Smart cascading filter generation - load base data once
        from datetime import datetime
        cache_key = f"_base_data_cache_{hash(str(datetime.now().date()))}"
        if not hasattr(get_all_learners_data, cache_key):
            setattr(get_all_learners_data, cache_key, pd.read_sql_query("SELECT \"Cohort #\", Status, Slot FROM \"Student List\"", conn))
            print("🔍 CACHE: Loading fresh filter data")
        
        base_data = getattr(get_all_learners_data, cache_key)
        
        # CASCADING FILTER LOGIC - each filter shows only relevant options
        
        # 1. Smart Cohorts: Apply status and slot filters, but not cohort filter
        cohorts_data = base_data.copy()
        if status_filter and len(status_filter) > 0:
            cohorts_data = cohorts_data[cohorts_data['Status'].isin(status_filter)]
        if slot_filter and len(slot_filter) > 0:
            slot_filter_temp = [slot[:6] for slot in slot_filter if slot]
            cohorts_data = cohorts_data[cohorts_data['Slot'].str[:6].isin(slot_filter_temp)]
        cohorts = sorted(cohorts_data['Cohort #'].dropna().unique())
        
        # 2. Smart Statuses: Apply cohort and slot filters, but not status filter
        statuses_data = base_data.copy()
        if cohort_filter and len(cohort_filter) > 0:
            try:
                cohort_filter_int = [int(c) for c in cohort_filter if c]
                statuses_data = statuses_data[statuses_data['Cohort #'].isin(cohort_filter_int)]
            except (ValueError, TypeError):
                cohort_filter_str = [str(c) for c in cohort_filter if c]
                statuses_data = statuses_data[statuses_data['Cohort #'].astype(str).isin(cohort_filter_str)]
        if slot_filter and len(slot_filter) > 0:
            slot_filter_temp = [slot[:6] for slot in slot_filter if slot]
            statuses_data = statuses_data[statuses_data['Slot'].str[:6].isin(slot_filter_temp)]
        statuses = sorted(statuses_data['Status'].dropna().unique())
        
        # 3. Smart Slots: Apply cohort and status filters, but not slot filter
        slots_data = base_data.copy()
        if cohort_filter and len(cohort_filter) > 0:
            try:
                cohort_filter_int = [int(c) for c in cohort_filter if c]
                slots_data = slots_data[slots_data['Cohort #'].isin(cohort_filter_int)]
            except (ValueError, TypeError):
                cohort_filter_str = [str(c) for c in cohort_filter if c]
                slots_data = slots_data[slots_data['Cohort #'].astype(str).isin(cohort_filter_str)]
        if status_filter and len(status_filter) > 0:
            slots_data = slots_data[slots_data['Status'].isin(status_filter)]
        slots = sorted(slots_data['Slot'].dropna().str.slice(0, 6).unique())
        
        print(f"🔍 CASCADING FILTERS: Cohorts: {len(cohorts)}, Statuses: {len(statuses)}, Slots: {len(slots)}")
        print(f"🔍 APPLIED FILTERS: cohort_filter={cohort_filter}, status_filter={status_filter}, slot_filter={slot_filter}")
        
        # NO DEDUPLICATION - Keep all rows
        # Counts - counting all rows including duplicates
        total_learners = len(working_df)  # This includes all matching rows
        print(f"🔍 LEARNERS DATA: Total learners after search: {total_learners}")
        active_statuses = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']
        active_learners_count = len(working_df[working_df['Status'].isin(active_statuses)])
        
        # Load gradesheet data for merging (optimized)
        gradesheet_df = pd.read_sql_query("SELECT * FROM Gradesheet", conn)
        
        # Quick dissertation phase calculation
        dissertation_phase_count = 0
        active_dissertation_statuses = ['Active', 'Active / Deferred In']
        
        print(f"🔍 OPTIMIZED: Skipping complex dissertation calculation for performance")
        
        # Pagination with safety checks
        total_pages = max(1, (total_learners + per_page - 1) // per_page) if total_learners > 0 else 1
        
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        print(f"🔍 LEARNERS DATA: Pagination - page: {page}, per_page: {per_page}, total_pages: {total_pages}, start_idx: {start_idx}, end_idx: {end_idx}")
        
        paginated_df = working_df.iloc[start_idx:end_idx]
        print(f"🔍 LEARNERS DATA: Paginated result has {len(paginated_df)} rows")
        
        # Merge with gradesheet for the paginated data to get course completion for display
        # Use left merge and handle potential duplicates
        paginated_df = paginated_df.merge(
            gradesheet_df[['Email', 'Cohort #', 'Courses Completed', 'Courses Incomplete']],
            on=['Email', 'Cohort #'],
            how='left'
        )
        
        # Remove any duplicates that might have been created during the merge
        paginated_df = paginated_df.drop_duplicates(subset=['Email', 'Cohort #', 'First Name', 'Last Name'])
        
        paginated_df['Courses Completed'] = paginated_df['Courses Completed'].fillna(0).astype(int)
        paginated_df['Courses Incomplete'] = paginated_df['Courses Incomplete'].fillna(0).astype(int)
        paginated_df['Net Completed'] = paginated_df['Courses Completed'] - paginated_df['Courses Incomplete']
        
        learners = paginated_df.to_dict('records')
        
        return {
            'learners': learners,
            'cohorts': cohorts,
            'slots': slots,
            'statuses': statuses,
            'active_learners_count': active_learners_count,
            'completed_learners_count': dissertation_phase_count,
            'total_courses': 7,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_learners,  # Standard pagination attribute
                'pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            }
        }
        
    except Exception as e:
        print(f"Error getting all learners data: {e}")
        return None
    finally:
        conn.close()
                # Add these routes to app.py after the authentication functions

@app.route('/test-auth')
@login_required
def test_auth():
    return jsonify({
        'user_id': session.get('user_id'),  # Changed from session to session
        'user_email': session.get('user_email'),  # Changed from session to session
        'role': session.get('role'),  # Changed from session to session
        'first_name': session.get('first_name'),  # Changed from session to session
        'last_name': session.get('last_name')  # Changed from session to session
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    """OTP-based login system"""
    
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'send_otp')
        
        # Debug logging
        print(f"🔍 DEBUG: Form action received: {action}")
        print(f"🔍 DEBUG: Form data: {dict(request.form)}")
        
        if action == 'send_otp':
            # Step 1: Send OTP
            email = request.form.get('email')
            email_account = request.form.get('email_account')
            
            print(f"🔍 DEBUG: Email: {email}")
            print(f"🔍 DEBUG: Email Account: {email_account}")
            
            if email and email_account:
                print(f"🔍 DEBUG: Calling send_login_otp with email={email}, account_key={email_account}")
                success, message = send_login_otp(email, account_key=email_account)
                print(f"🔍 DEBUG: OTP Result - Success: {success}, Message: {message}")
                
                if success:
                    print(f"✅ DEBUG: OTP sent successfully, showing OTP form")
                    flash('Login code sent to your email!', 'success')
                    return render_template('login.html', 
                                         step='verify', 
                                         email=email,
                                         email_accounts=get_email_accounts(),
                                         show_otp_form=True)
                else:
                    print(f"❌ DEBUG: OTP failed: {message}")
                    flash(f'Error: {message}', 'error')
            elif not email:
                print(f"❌ DEBUG: No email provided")
                flash('Please enter your email address', 'error')
            elif not email_account:
                print(f"❌ DEBUG: No email account provided")
                flash('Please select an email account to send OTP from', 'error')
        
        elif action == 'verify_otp':
            # Step 2: Verify OTP
            email = request.form.get('email')
            otp_code = request.form.get('otp_code')
            
            if email and otp_code:
                success, message = verify_login_otp(email, otp_code)
                
                if success:
                    # Get user info and create session
                    user_info = get_user_by_email(email)
                    if user_info:
                        session['user_id'] = user_info['id']
                        session['user_email'] = user_info['email']
                        session['user_name'] = f"{user_info['first_name']} {user_info['last_name']}"
                        session['role'] = user_info['role']
                        
                        flash(f'Welcome back, {user_info["first_name"]}!', 'success')
                        
                        # Redirect to intended page or dashboard
                        next_page = request.args.get('next')
                        return redirect(next_page) if next_page else redirect(url_for('dashboard'))
                    else:
                        flash('User information not found', 'error')
                else:
                    flash(f'Error: {message}', 'error')
                    return render_template('login.html', 
                                         step='verify', 
                                         email=email,
                                         email_accounts=get_email_accounts(),
                                         show_otp_form=True)
            else:
                flash('Please enter both email and OTP code', 'error')
    
    # GET request or form errors - show initial login form
    return render_template('login.html', step='email', show_otp_form=False, email_accounts=get_email_accounts())


@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP code"""
    
    email = request.form.get('email')
    if email:
        success, message = send_login_otp(email, account_key="primary")
        
        if success:
            flash('New login code sent to your email!', 'success')
        else:
            flash(f'Error: {message}', 'error')
    else:
        flash('Email address required', 'error')
    
    return render_template('login.html', 
                         step='verify', 
                         email=email,
                         email_accounts=get_email_accounts(),
                         show_otp_form=True)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))
  
                 
@app.route('/upload_database', methods=['POST'])
@login_required
def upload_database():
    """Handle database upload and processing"""
    if 'excel_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['excel_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            # Save the uploaded file temporarily
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            
            # Run the db.py script to process the Excel file
            db_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db.py')
            
            # Use subprocess to run the db.py script with the uploaded file
            result = subprocess.run([
                'python', db_script_path, '--file', temp_path
            ], capture_output=True, text=True)
            
            # Clean up temporary file
            os.remove(temp_path)
            
            if result.returncode == 0:
                return jsonify({'success': True, 'message': 'Database updated successfully!'})
            else:
                return jsonify({'success': False, 'message': f'Error processing file: {result.stderr}'})
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})
    else:
        return jsonify({'success': False, 'message': 'Invalid file format. Please upload an Excel file (.xlsx or .xls)'})
    return redirect(url_for('dashboard'))



@app.route('/')
@login_required
def dashboard():
    try:
        # Debug: Print session info
        print(f"🔍 SESSION DEBUG: {dict(session)}")
        print(f"🔍 USER ROLE: {session.get('role', 'NOT SET')}")
        cohort_filter = request.args.getlist('cohort')
        slot_filter = request.args.getlist('slot')
        status_filter = request.args.getlist('status')
        search_filter = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        
        print(f"🔍 DASHBOARD: Getting dashboard data...")
        # Get all learners for frontend pagination (set per_page to a large number)
        data = get_dashboard_data(cohort_filter, slot_filter, status_filter, search_filter, page, per_page=1000)
        if not data:
            print("❌ DASHBOARD: get_dashboard_data returned None")
            return "Error loading data", 500
        
        print(f"✅ DASHBOARD: Dashboard data loaded successfully")
        
        # Get dissertation analytics using the same function as dissertation page
        print(f"🔍 DASHBOARD: Getting dissertation analytics...")
        from utils.dissertation_analytics import get_dissertation_analytics
        dissertation_data = get_dissertation_analytics(cohort_filter if cohort_filter else None)
        print(f"🔍 DASHBOARD: Dissertation data result: {dissertation_data is not None}")
        
        if dissertation_data:
            print(f"🔍 DASHBOARD: Adding dissertation data to template - Total: {dissertation_data['total_dissertation']}")
            data['dissertation_analytics'] = dissertation_data
        else:
            print(f"🔍 DASHBOARD: Using default dissertation data")
            # Create default structure matching the utils function
            data['dissertation_analytics'] = {
                'total_dissertation': 0,
                'completed_count': 0,
                'total_approvals': 0,
                'total_not_approved': 0,
                'overall_pending_review': 0,
                'topic_proposal': {'submitted': {'count': 0}, 'approved': {'count': 0}},
                'irb': {'submitted': {'count': 0}, 'approved': {'count': 0}},
                'research_proposal': {'submitted': {'count': 0}, 'approved': {'count': 0}},
                'final_defense': {'submitted': {'count': 0}, 'approved': {'count': 0}},
                'cohorts': [],
                'last_updated': None
            }
        
        # Get coursework analytics
        print(f"🔍 DASHBOARD: Getting coursework analytics...")
        coursework_stats = get_coursework_dashboard_stats()
        coursework_overview = get_coursework_overview()
        live_session_data = get_live_session_analytics()
        
        data['coursework_stats'] = coursework_stats
        data['coursework_overview'] = coursework_overview
        data['live_session_data'] = live_session_data
        print(f"✅ DASHBOARD: Coursework data loaded")
        
        # Get user information from database
        user_info = None
        if 'user_email' in session:
            user_info = get_user_by_email(session['user_email'])
            if user_info:
                # Update session with latest user info
                session['first_name'] = user_info.get('first_name', 'User')
                session['last_name'] = user_info.get('last_name', '')
                session['role'] = user_info.get('role', 'user')
        
        # Calculate active learners count (Active + Active / Deferred In)
        print(f"🔍 DASHBOARD: Calculating active learners count...")
        try:
            conn = get_db_connection()
            if conn:
                import pandas as pd
                student_list_df = pd.read_sql_query("SELECT * FROM \"Student List\"", conn)
                active_statuses = ['Active', 'Active / Deferred In']
                active_students = student_list_df[student_list_df['Status'].isin(active_statuses)]
                active_learners_count = len(active_students['Email'].dropna().unique())
                conn.close()
                print(f"✅ DASHBOARD: Active learners count: {active_learners_count}")
            else:
                active_learners_count = 710  # Fallback value
                print(f"⚠️ DASHBOARD: Using fallback active learners count: {active_learners_count}")
        except Exception as e:
            print(f"❌ DASHBOARD: Error calculating active learners: {e}")
            active_learners_count = 710  # Fallback value
        
        # Add selected filters to template context
        data['selected_cohorts'] = cohort_filter
        data['selected_slots'] = slot_filter
        data['selected_statuses'] = status_filter
        data['last_updated'] = get_last_updated_time()
        data['user_info'] = user_info
        data['active_learners_count'] = active_learners_count
        
        print(f"✅ DASHBOARD: Rendering template with data")
        return render_template('dashboard.html', **data)
        
    except Exception as e:
        print(f"❌ DASHBOARD ERROR: {e}")
        print(f"❌ DASHBOARD TRACEBACK: {traceback.format_exc()}")
        return f"Dashboard Error: {str(e)}", 500

# In the learners route, remove country filter handling

@app.route('/test-pagination')
def test_pagination():
    """Simple pagination test without authentication"""
    try:
        # Get parameters
        page = max(1, request.args.get('page', 1, type=int))
        per_page = request.args.get('per_page', 10, type=int)
        
        # Validate per_page
        if per_page not in [10, 25, 50, 100]:
            per_page = 10
        
        print(f"🧪 TEST PAGINATION: page={page}, per_page={per_page}")
        
        # Get data
        data = get_all_learners_data(page=page, per_page=per_page)
        learner_stats = get_learner_statistics()
        
        if not data:
            data = {
                'learners': [],
                'pagination': {'page': 1, 'per_page': per_page, 'pages': 0, 'has_prev': False, 'has_next': False}
            }
        
        data.update(learner_stats)
        
        return render_template('test_pagination.html', **data)
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/debug-learners-data')
def debug_learners_data():
    """Debug route to test learners data without authentication"""
    try:
        print("🔍 DEBUG LEARNERS: Starting...")
        
        # Test different per_page values
        results = {}
        for per_page in [10, 25, 50]:
            print(f"🔍 DEBUG LEARNERS: Testing per_page={per_page}")
            data = get_all_learners_data(page=1, per_page=per_page)
            results[f'per_page_{per_page}'] = {
                'learners_count': len(data['learners']) if data and 'learners' in data else 0,
                'total_learners': data.get('total_learners', 0) if data else 0,
                'pagination': data.get('pagination') if data else None
            }
        
        # Get learner statistics
        learner_stats = get_learner_statistics()
        
        return jsonify({
            'statistics': learner_stats,
            'per_page_tests': results
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/test-db')
def test_db():
    """Test database connectivity without authentication"""
    try:
        conn = get_db_connection()
        if not conn:
            return "❌ Database connection failed", 500
        
        cursor = conn.cursor()
        
        # Test basic queries
        results = {}
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        results['tables'] = [table[0] for table in tables]
        
        # Test Student List table
        try:
            cursor.execute('SELECT COUNT(*) FROM "Student List"')
            student_count = cursor.fetchone()[0]
            results['student_count'] = student_count
        except Exception as e:
            results['student_list_error'] = str(e)
        
        # Test Gradesheet table
        try:
            cursor.execute('SELECT COUNT(*) FROM "Gradesheet"')
            gradesheet_count = cursor.fetchone()[0]
            results['gradesheet_count'] = gradesheet_count
        except Exception as e:
            results['gradesheet_error'] = str(e)
        
        # Test dashboard data function
        try:
            dashboard_data = get_dashboard_data()
            results['dashboard_data_success'] = dashboard_data is not None
            if dashboard_data:
                results['dashboard_keys'] = list(dashboard_data.keys())
        except Exception as e:
            results['dashboard_data_error'] = str(e)
        
        conn.close()
        
        return jsonify({
            'status': '✅ Database tests completed',
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'status': '❌ Database test failed',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/learners')
@login_required
def learners():
    try:
        print("🔍 LEARNERS ROUTE: Starting...")
        print(f"🔍 LEARNERS ROUTE: Request args: {dict(request.args)}")
        # Get filter parameters with multi-select support
        selected_cohorts = request.args.getlist('cohort')
        selected_slots = request.args.getlist('slot')
        selected_statuses = request.args.getlist('status')
        # Remove country filter
        search_query = request.args.get('search', '').strip()
        page = max(1, request.args.get('page', 1, type=int))
        per_page = request.args.get('per_page', 10, type=int)
        
        # Validate per_page parameter (must be one of the allowed values)
        allowed_per_page = [10, 25, 50, 100]
        if per_page not in allowed_per_page:
            per_page = 10
            
        print(f"🔍 LEARNERS ROUTE: Parsed params - page: {page}, per_page: {per_page}, cohorts: {selected_cohorts}, slots: {selected_slots}, statuses: {selected_statuses}, search: '{search_query}'")

        # Get learner statistics for the cards
        print("🔍 LEARNERS ROUTE: Getting statistics...")
        learner_stats = get_learner_statistics()
        print(f"🔍 LEARNERS ROUTE: Statistics result: {learner_stats}")
        
        # Use the existing function to get learners data (remove country_filter)
        print("🔍 LEARNERS ROUTE: Getting learners data...")
        data = get_all_learners_data(
            cohort_filter=selected_cohorts,
            slot_filter=selected_slots, 
            status_filter=selected_statuses,
            search_filter=search_query,
            page=page,
            per_page=per_page
        )
        
        if not data:
            flash('Error loading learners data', 'error')
            data = {
                'learners': [],
                'cohorts': [],
                'slots': [],
                'statuses': [],
                # Remove countries
                'pagination': {
                    'page': 1, 
                    'per_page': per_page, 
                    'total': 0, 
                    'pages': 0,
                    'has_prev': False,
                    'has_next': False,
                    'prev_num': None,
                    'next_num': None
                },
                'total_learners': 0,
                'active_learners': 0,
                'failed_dropout': 0,
                'completed_learners': 0,
                'inactive_learners': 0
            }

        # Add selected filters and last updated time (remove country)
        data['selected_cohorts'] = selected_cohorts
        data['selected_slots'] = selected_slots
        data['selected_statuses'] = selected_statuses
        data['last_updated'] = get_last_updated_time()

        # Ensure statistics are always included, but preserve filtered total_learners
        print("🔍 LEARNERS ROUTE: Updating data with statistics...")
        filtered_total_learners = data.get('total_learners', 0)  # Save filtered count
        data.update(learner_stats)
        
        # If we have filters applied, use the filtered count for total_learners
        if selected_cohorts or selected_slots or selected_statuses or search_query:
            data['total_learners'] = filtered_total_learners
            print(f"🔍 LEARNERS ROUTE: Using filtered total_learners: {filtered_total_learners}")
        else:
            print(f"🔍 LEARNERS ROUTE: Using unfiltered total_learners: {data.get('total_learners', 'NOT FOUND')}")
            
        print(f"🔍 LEARNERS ROUTE: Final data keys: {list(data.keys())}")
        print(f"🔍 LEARNERS ROUTE: Final total_learners: {data.get('total_learners', 'NOT FOUND')}")
        return render_template('learners.html', **data)

    except Exception as e:
        flash(f'Error loading learners data: {str(e)}', 'error')
        # Return empty data structure on error with all required variables
        return render_template('learners.html',
                            learners=[],
                            cohorts=[],
                            slots=[],
                            statuses=[],
                            selected_cohorts=[],
                            selected_slots=[],
                            selected_statuses=[],
                            pagination={
                                'page': 1, 
                                'per_page': 10, 
                                'total': 0, 
                                'pages': 0,
                                'has_prev': False,
                                'has_next': False,
                                'prev_num': None,
                                'next_num': None
                            },
                            total_learners=0,
                            active_learners=0,
                            failed_dropout=0,
                            completed_learners=0,
                            inactive_learners=0,
                            last_updated=get_last_updated_time())
        
        
# Add this to app.py after the existing imports and before the routes

def get_dissertation_data(email, cohort_number):
    """Get dissertation data for a learner in specific cohort"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Check if Dissertation table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Dissertation'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("Dissertation table does not exist")
            return None
        
        # Get dissertation data
        dissertation_query = """
            SELECT * FROM Dissertation WHERE "Email" = ? AND "Cohort #" = ?
        """
        print(f"Querying dissertation data for: {email}, cohort: {cohort_number}")
        dissertation_df = pd.read_sql_query(dissertation_query, conn, params=(email, cohort_number))
        
        print(f"Found {len(dissertation_df)} dissertation records")
        
        if not dissertation_df.empty:
            dissertation_data = dissertation_df.iloc[0].to_dict()
            
            # Debug: Print all dissertation data
            print(f"=== DISSERTATION DATA FOR {email} ===")
            for key, value in dissertation_data.items():
                print(f"  {key}: {value}")
            print("=====================================")
            
            # Ensure all values are properly handled
            for key, value in dissertation_data.items():
                if pd.isna(value):
                    dissertation_data[key] = None
                    
            return dissertation_data
        
        print("No dissertation data found for this email and cohort")
        return None
        
    except Exception as e:
        print(f"Error getting dissertation data: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return None
    finally:
        conn.close()

@app.route('/learner/<user_id>')
@login_required
def learner_profile(user_id):
    """Display individual learner profile with detailed information across all cohorts"""
    
    conn = get_db_connection()
    if not conn:
        return "Error connecting to database", 500
    
    try:
        # Get ALL learner entries from Student List (across all cohorts)
        student_query = """
            SELECT * FROM "Student List" WHERE "User ID" = ? ORDER BY "Cohort #"
        """
        student_df = pd.read_sql_query(student_query, conn, params=(user_id,))
        
        if student_df.empty:
            return "Learner not found", 404
        
        # Use the first entry as the primary learner info
        learner_info = student_df.iloc[0].to_dict()
        email = learner_info['Email']
        
        # Collect data for all cohorts
        all_cohorts_data = []
        
        for _, cohort_row in student_df.iterrows():
            cohort_number = cohort_row['Cohort #']
            
            # Get academic info
            gradesheet_query = """
                SELECT * FROM Gradesheet WHERE Email = ? AND "Cohort #" = ?
            """
            gradesheet_df = pd.read_sql_query(gradesheet_query, conn, params=(email, cohort_number))
            
            academic_info = {}
            courses = []
            cgpa = 0
            courses_completed = 0
            
            if not gradesheet_df.empty:
                academic_info = gradesheet_df.iloc[0].to_dict()
                cgpa = academic_info.get('Overall CGPA', 0)
                courses_completed = academic_info.get('Courses Completed', 0)
                
                # Get course details
                course_columns = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                                 'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
                
                for course_col in course_columns:
                    if course_col in academic_info and pd.notna(academic_info.get(course_col)):
                        course_name = course_col.replace(' Grade', '')
                        credit_col = course_col.replace('Grade', 'Credit')
                        credit = academic_info.get(credit_col, 'N/A')
                        
                        grade_value = academic_info[course_col]
                        is_low_grade = False
                        
                        if grade_value and isinstance(grade_value, str):
                            is_low_grade = grade_value in LOW_GRADES
                        
                        courses.append({
                            'name': course_name,
                            'grade': grade_value,
                            'credit': credit,
                            'is_low_grade': is_low_grade
                        })
            
            # Get dissertation data - FIXED: Use the function with both email and cohort
            dissertation_info = get_dissertation_data(email, cohort_number)
            
            cohort_data = {
                'cohort_number': cohort_number,
                'status': cohort_row['Status'],
                'slot': cohort_row['Slot'],
                'batch': cohort_row['Batch'],
                'cgpa': cgpa,
                'courses_completed': courses_completed,
                'courses': courses,
                'dissertation': dissertation_info
            }
            
            all_cohorts_data.append(cohort_data)
        
        return render_template('learner_profile.html', 
                             learner=learner_info, 
                             all_cohorts_data=all_cohorts_data,
                             last_updated=get_last_updated_time())
        
    except Exception as e:
        print(f"Error getting learner profile: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return "Error loading learner profile", 500
    finally:
        conn.close()
        
@app.route('/api/data')
@login_required
def api_data():
    cohort_filter = request.args.get('cohort')
    slot_filter = request.args.get('slot')
    if slot_filter:
        slot_filter = slot_filter[:6]
    status_filter = request.args.get('status')
    
    data = get_dashboard_data(cohort_filter, slot_filter, status_filter)
    if not data:
        return jsonify({"error": "Failed to get data"}), 500
    return render_template("automation_tools.html")

@app.route("/automation-tools")
@login_required
def automation_tools():
    """Automation tools page"""
    return render_template("automation_tools.html")

# Add these route handlers for direct access to pages
@app.route("/document")
@login_required
def document_home():
    return render_template("document_creation.html")

@app.route("/reminder")
@login_required
def reminder_home():
    return redirect(url_for('reminder.reminder_home'))

@app.route("/campaigns")
@login_required
def campaigns_home():
    return redirect(url_for('campaigns.campaigns_home'))
@app.route("/folders")
@login_required
def folder_home():
    return render_template("folder_creator_ui.html")

@app.route("/chatbot")
@login_required
def chatbot():
    """Main chatbot page"""
    return render_template("chatbot.html")




@app.route('/test-admin')
@login_required
def test_admin():
    """Test route to check admin access"""
    return f"""
    <h1>Admin Access Test</h1>
    <p><strong>Session Data:</strong></p>
    <pre>{dict(session)}</pre>
    <p><strong>Role:</strong> {session.get('role', 'NOT SET')}</p>
    <p><strong>User Role:</strong> {session.get('user_role', 'NOT SET')}</p>
    <p><strong>Admin Access:</strong> {'YES' if session.get('role') == 'admin' else 'NO'}</p>
    <a href="/">Back to Dashboard</a>
    """


@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    """Admin panel for user management"""
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_user':
            # Add new user
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            role = request.form.get('role')
            
            if first_name and last_name and email and role:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Check if user already exists
                    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                    if cursor.fetchone():
                        flash(f'User with email {email} already exists!', 'error')
                    else:
                        # Insert new user (no password needed for OTP system)
                        cursor.execute("""
                            INSERT INTO users (first_name, last_name, email, role, is_active, created_at)
                            VALUES (?, ?, ?, ?, 1, datetime('now'))
                        """, (first_name, last_name, email, role))
                        
                        conn.commit()
                        flash(f'User {first_name} {last_name} added successfully!', 'success')
                    
                    conn.close()
                except Exception as e:
                    flash(f'Error adding user: {str(e)}', 'error')
            else:
                flash('All fields are required', 'error')
        
        elif action == 'edit_user':
            # Edit existing user
            user_id = request.form.get('user_id')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            role = request.form.get('role')
            
            if user_id and first_name and last_name and email and role:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE users 
                        SET first_name = ?, last_name = ?, email = ?, role = ?
                        WHERE id = ?
                    """, (first_name, last_name, email, role, user_id))
                    
                    conn.commit()
                    conn.close()
                    
                    flash(f'User {first_name} {last_name} updated successfully!', 'success')
                except Exception as e:
                    flash(f'Error updating user: {str(e)}', 'error')
            else:
                flash('All fields are required for user update', 'error')
        
        elif action == 'toggle_status':
            # Toggle user active status
            user_id = request.form.get('user_id')
            
            if user_id:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Get current status
                    cursor.execute("SELECT is_active, first_name, last_name FROM users WHERE id = ?", (user_id,))
                    user_data = cursor.fetchone()
                    
                    if user_data:
                        current_status = user_data[0]
                        user_name = f"{user_data[1]} {user_data[2]}"
                        new_status = 0 if current_status else 1
                        
                        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
                        conn.commit()
                        
                        status_text = "activated" if new_status else "deactivated"
                        flash(f'User {user_name} {status_text} successfully!', 'success')
                    else:
                        flash('User not found', 'error')
                    
                    conn.close()
                except Exception as e:
                    flash(f'Error updating user status: {str(e)}', 'error')
            else:
                flash('User ID required', 'error')
        
        elif action == 'delete_user':
            # Delete user
            user_id = request.form.get('user_id')
            
            # Prevent users from deleting themselves
            if user_id and int(user_id) == session.get('user_id'):
                flash('You cannot delete your own account!', 'error')
            elif user_id:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Get user name before deletion
                    cursor.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
                    user_data = cursor.fetchone()
                    
                    if user_data:
                        user_name = f"{user_data[0]} {user_data[1]}"
                        
                        # Delete the user
                        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                        conn.commit()
                        
                        flash(f'User {user_name} deleted successfully!', 'success')
                    else:
                        flash('User not found', 'error')
                    
                    conn.close()
                except Exception as e:
                    flash(f'Error deleting user: {str(e)}', 'error')
            else:
                flash('User ID required', 'error')
        
        # Redirect to prevent form resubmission
        return redirect(url_for('admin_users'))
    
    # GET request - show the admin panel
    conn = get_db_connection()
    if not conn:
        flash('Error connecting to database', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Get all users
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, first_name, last_name, email, role, is_active, created_at 
            FROM users 
            ORDER BY id ASC
        """)
        users = cursor.fetchall()
        
        # Convert to list of dictionaries
        users_list = []
        for user in users:
            users_list.append({
                'id': user[0],
                'first_name': user[1],
                'last_name': user[2],
                'email': user[3],
                'role': user[4],
                'is_active': bool(user[5]),
                'created_at': user[6] if user[6] else 'N/A'
            })
        
        return render_template('admin_users.html', users=users_list, last_updated=get_last_updated_time())
        
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        flash('Error loading admin panel', 'error')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/coursework')
@login_required
def coursework():
    """Coursework management page with live sessions"""
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('dashboard'))
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Get filter parameters
        course_filter = request.args.get('course', '')
        attendance_filter = request.args.get('attendance', '')
        search_filter = request.args.get('search', '')
        
        # Get coursework data
        coursework_stats = get_coursework_dashboard_stats()
        
        # Get live sessions data from actual database structure
        query = '''
        SELECT 
            rowid as id,
            [Program] as course_code,
            [Program] as program,
            [Day] as day,
            [LS Date] as session_date,
            [Month] as month,
            [Year] as year,
            [Cohort Name] as cohort_name,
            [Track] as track,
            [Topic] as session_topic,
            [Topic] as topic,
            [Agenda] as agenda,
            [Speaker Bio] as speaker_bio,
            [SME_Prof_Name] as instructor,
            [Start Time] as start_time,
            [End Time] as end_time,
            [Session Type] as session_type,
            [Peak Attendance #] as peak_attendance,
            [Unique attendees #] as unique_attendees,
            [Students Who Rated #] as students_rated,
            [Avg. Rating #] as avg_rating,
            [Scheduled Duration (in Hrs)] as scheduled_duration,
            [Actual Duration] as actual_duration,
            rowid as session_number
        FROM [Live Session]
        ORDER BY [Year], [LS Date], [Start Time]
        '''
        
        sessions_df = pd.read_sql_query(query, conn)
        all_sessions = sessions_df.to_dict('records')
        
        # Process sessions to add calculated fields
        for session in all_sessions:
            # Calculate attendance rate
            if session['peak_attendance'] and session['unique_attendees']:
                session['attendance_rate'] = round((session['peak_attendance'] / max(session['unique_attendees'], 1)) * 100, 1)
                session['attended_students'] = session['peak_attendance']
                session['total_students'] = session['unique_attendees']
            else:
                session['attendance_rate'] = 0
                session['attended_students'] = 0
                session['total_students'] = 0
            
            # Convert duration to minutes
            if session['scheduled_duration']:
                session['duration_minutes'] = int(session['scheduled_duration'] * 60)
            else:
                session['duration_minutes'] = 90
            
            # Format session date
            if session['session_date']:
                try:
                    # Handle different date formats
                    if isinstance(session['session_date'], (int, float)):
                        # Excel date serial number
                        from datetime import datetime, timedelta
                        excel_date = datetime(1900, 1, 1) + timedelta(days=int(session['session_date']) - 2)
                        session['session_date'] = excel_date.strftime('%Y-%m-%d')
                    elif isinstance(session['session_date'], str):
                        # Already formatted
                        pass
                except:
                    session['session_date'] = 'N/A'
        
        # Apply server-side filtering
        filtered_sessions = all_sessions
        
        if course_filter:
            filtered_sessions = [s for s in filtered_sessions if course_filter.lower() in s['course_code'].lower()]
        
        if attendance_filter:
            if attendance_filter == 'high':
                filtered_sessions = [s for s in filtered_sessions if s['attendance_rate'] >= 80]
            elif attendance_filter == 'medium':
                filtered_sessions = [s for s in filtered_sessions if 60 <= s['attendance_rate'] < 80]
            elif attendance_filter == 'low':
                filtered_sessions = [s for s in filtered_sessions if s['attendance_rate'] < 60]
        
        if search_filter:
            search_lower = search_filter.lower()
            filtered_sessions = [s for s in filtered_sessions if 
                               search_lower in s['session_topic'].lower() or 
                               search_lower in s['course_code'].lower() or
                               search_lower in (s['instructor'] or '').lower()]
        
        # Calculate pagination
        total_sessions = len(filtered_sessions)
        offset = (page - 1) * per_page
        sessions = filtered_sessions[offset:offset + per_page]
        
        # Create pagination object
        class Pagination:
            def __init__(self, page, per_page, total):
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
        
        pagination = Pagination(page, per_page, total_sessions)
        
        # Get program-wise session summary
        course_summary_query = '''
        SELECT 
            [Program] as program_name,
            [Program] as course_code,
            [Program] as course_name,
            COUNT(*) as total_sessions,
            ROUND(AVG([Peak Attendance #]), 1) as avg_peak_attendance,
            ROUND(AVG([Unique attendees #]), 1) as avg_unique_attendees,
            ROUND(AVG([Avg. Rating #]), 2) as avg_rating,
            COUNT(CASE WHEN [Avg. Rating #] > 0 THEN 1 END) as sessions_with_ratings
        FROM [Live Session]
        WHERE [Program] IS NOT NULL
        GROUP BY [Program]
        ORDER BY [Program]
        '''
        
        course_summary_df = pd.read_sql_query(course_summary_query, conn)
        course_summary = course_summary_df.to_dict('records')
        
        # Process course summary to add calculated fields
        for course in course_summary:
            # Calculate attendance rate
            if course['avg_peak_attendance'] and course['avg_unique_attendees']:
                course['avg_attendance_rate'] = round((course['avg_peak_attendance'] / max(course['avg_unique_attendees'], 1)) * 100, 1)
            else:
                course['avg_attendance_rate'] = 0
        
        conn.close()
        
        return render_template('coursework.html', 
                             coursework_stats=coursework_stats,
                             sessions=sessions,
                             course_summary=course_summary,
                             pagination=pagination,
                             current_filters={
                                 'course': course_filter,
                                 'attendance': attendance_filter,
                                 'search': search_filter
                             },
                             last_updated=get_last_updated_time())
    except Exception as e:
        print(f"Error loading coursework page: {e}")
        flash('Error loading coursework data', 'error')
        return redirect(url_for('dashboard'))



@app.route('/coursework/upload-attendance', methods=['POST'])
@login_required
def upload_attendance():
    """Upload attendance data from Excel file"""
    print("🔄 ATTENDANCE UPLOAD: Starting upload process...")
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file selected. Please choose an Excel file to upload.'
            })
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected. Please choose an Excel file to upload.'
            })
        
        # Check file extension
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({
                'success': False,
                'message': 'Invalid file format. Please upload an Excel file (.xlsx or .xls).'
            })
        
        # Read Excel file
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error reading Excel file: {str(e)}. Please check the file format.'
            })
        
        # Check for different possible column formats
        # Format 1: Standard format (Student Name, Session ID, Attended)
        standard_columns = ['Student Name', 'Session ID', 'Attended']
        # Format 2: Session export format (User Name, Email, Time in Session, etc.)
        session_columns = ['User Name (Original Name)', 'Email', 'Time in Session (minutes)']
        
        has_standard_format = all(col in df.columns for col in standard_columns)
        has_session_format = all(col in df.columns for col in session_columns)
        
        if not has_standard_format and not has_session_format:
            return jsonify({
                'success': False,
                'message': f'Invalid file format. Please ensure your Excel file has either:\n\nFormat 1: Student Name, Session ID, Attended (Yes/No)\nOR\nFormat 2: User Name (Original Name), Email, Time in Session (minutes), Join Date, Leave Time'
            })
        
        # Process attendance data
        processed_records = 0
        conn = get_db_connection()
        
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection error. Please try again later.'
            })
        
        try:
            # Immediate cleanup: Drop old tables if they exist
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS attendance_uploads')
            cursor.execute('DROP TABLE IF EXISTS attendance_records')
            print("🗑️ Cleaned up old attendance tables: attendance_uploads, attendance_records")
            
            for index, row in df.iterrows():
                # Initialize variables
                email = None
                session_time = None
                
                if has_standard_format:
                    # Process standard format
                    student_name = str(row['Student Name']).strip()
                    session_id = str(row['Session ID']).strip()
                    attended = str(row['Attended']).strip().lower()
                    
                    # Skip empty rows
                    if not student_name or not session_id:
                        continue
                    
                    # Convert attendance to boolean
                    attendance_status = attended in ['yes', 'y', '1', 'true', 'present']
                    
                elif has_session_format:
                    # Process session export format
                    student_name = str(row['User Name (Original Name)']).strip()
                    email = str(row['Email']).strip()
                    time_in_session = row.get('Time in Session (minutes)', 0)
                    
                    # Skip empty rows
                    if not student_name or not email:
                        continue
                    
                    # Generate session ID from join date or use email
                    session_id = email  # Use email as session identifier
                    
                    # Determine attendance based on time in session (>5 minutes = attended)
                    try:
                        session_time = float(time_in_session) if time_in_session else 0
                        attendance_status = session_time > 5  # More than 5 minutes = attended
                    except (ValueError, TypeError):
                        attendance_status = False
                
                # Insert or update attendance record
                # For now, we'll create a simple attendance log table
                cursor = conn.cursor()
                # Create comprehensive attendance table (only once, preserve existing data)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_name TEXT NOT NULL,
                        email TEXT,
                        session_id TEXT NOT NULL,
                        session_topic TEXT,
                        session_date DATE,
                        join_time TIMESTAMP,
                        leave_time TIMESTAMP,
                        time_in_session REAL,
                        attended BOOLEAN NOT NULL,
                        is_guest BOOLEAN DEFAULT 0,
                        attendance_percentage REAL,
                        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        uploaded_by TEXT,
                        source TEXT DEFAULT 'upload'
                    )
                ''')
                
                # Create indexes for better performance (only if they don't exist)
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_attendance_email_session 
                    ON attendance(email, session_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_attendance_date 
                    ON attendance(session_date)
                ''')
                
                # Prepare additional data based on format
                if has_session_format:
                    email_field = email
                    time_field = session_time
                    is_guest = row.get('Is Guest', False)
                    
                    # Convert timestamps to strings to avoid SQLite binding errors
                    join_date_raw = row.get('Join Date', None)
                    leave_time_raw = row.get('Leave Time', None)
                    
                    join_date = str(join_date_raw) if join_date_raw is not None and not pd.isna(join_date_raw) else None
                    leave_time = str(leave_time_raw) if leave_time_raw is not None and not pd.isna(leave_time_raw) else None
                    
                    # Calculate attendance percentage (time in session / total session duration)
                    # Assuming 90 minutes as standard session duration
                    attendance_percentage = min(100, (session_time / 90) * 100) if session_time else 0
                else:
                    email_field = None
                    time_field = None
                    is_guest = False
                    join_date = None
                    leave_time = None
                    attendance_percentage = 100 if attendance_status else 0
                
                # Check for existing duplicate records using email + name + date
                # Extract date from session data if available
                session_date = None
                if has_session_format and join_date:
                    # Try to extract date from join_date
                    try:
                        if isinstance(join_date, str) and len(join_date) >= 10:
                            session_date = join_date[:10]  # Extract YYYY-MM-DD part
                    except:
                        session_date = None
                
                if email_field and session_date:
                    # Use email + name + date as unique identifier
                    cursor.execute('''
                        SELECT COUNT(*) FROM attendance 
                        WHERE email = ? AND student_name = ? AND DATE(join_time) = ?
                    ''', (email_field, student_name, session_date))
                elif email_field:
                    # Fallback: Use email + name + session_id
                    cursor.execute('''
                        SELECT COUNT(*) FROM attendance 
                        WHERE email = ? AND student_name = ? AND session_id = ?
                    ''', (email_field, student_name, session_id))
                else:
                    # For standard format without email, use name + session_id
                    cursor.execute('''
                        SELECT COUNT(*) FROM attendance 
                        WHERE student_name = ? AND session_id = ?
                    ''', (student_name, session_id))
                
                duplicate_count = cursor.fetchone()[0]
                
                if duplicate_count > 0:
                    identifier = f"{student_name} - {email_field or 'No Email'} - {session_date or session_id}"
                    print(f"⚠️ ATTENDANCE: Skipping duplicate record for {identifier}")
                    continue  # Skip this record
                
                # Insert comprehensive attendance record (only if not duplicate)
                print(f"🔄 ATTENDANCE: Inserting new record for {student_name}")
                
                cursor.execute('''
                    INSERT INTO attendance (
                        student_name, email, session_id, time_in_session, attended, 
                        is_guest, attendance_percentage, uploaded_by, source,
                        join_time, leave_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_name, email_field, session_id, time_field, attendance_status,
                    is_guest, attendance_percentage, session.get('email', 'Unknown'), 'upload',
                    join_date, leave_time
                ))
                
                processed_records += 1
            
            # Update Live Session table with attendance data if possible
            try:
                update_live_session_attendance(conn, processed_records)
            except Exception as e:
                print(f"Warning: Could not update Live Session table: {e}")
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Successfully processed {processed_records} new attendance records from your Excel file. Duplicate records were automatically skipped. Data has been appended to the attendance table and integrated with live session data.'
            })
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Error processing attendance data: {str(e)}. Please check your data format and try again.'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}. Please try again.'
        })


@app.route('/coursework/upload-ratings', methods=['POST'])
@login_required
def upload_ratings():
    """Upload ratings data from Excel file"""
    print("🔄 RATINGS UPLOAD: Starting upload process...")
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file selected. Please choose an Excel file to upload.'
            })
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected. Please choose an Excel file to upload.'
            })
        
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({
                'success': False,
                'message': 'Invalid file format. Please upload an Excel file (.xlsx or .xls).'
            })
        
        # Read Excel file
        print(f"🔄 RATINGS UPLOAD: Reading Excel file: {file.filename}")
        try:
            df = pd.read_excel(file)
            print(f"🔄 RATINGS UPLOAD: Successfully read Excel file with {len(df)} rows and {len(df.columns)} columns")
        except Exception as e:
            print(f"❌ RATINGS UPLOAD: Error reading Excel file: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error reading Excel file: {str(e)}. Please ensure the file is not corrupted and try again.'
            })
        
        if df.empty:
            return jsonify({
                'success': False,
                'message': 'The uploaded Excel file is empty. Please upload a file with data.'
            })
        
        # Expected columns for ratings upload (flexible matching)
        expected_columns = [
            'User Name', 'Email Address', 'Submitted Date and Time', 'Collected from', 'Topic',
            'Meeting/Webinar ID', 'I am satisfied with the session overall.',
            'The topics covered during this session were clear and aligned with the learning objectives.',
            'The professor demonstrated strong subject matter expertise, engaged learners, and addressed questions effectively.',
            'The slides and reference materials presented during the session enhanced my understanding of the topic.',
            'What is one key insight or learning you will carry forward from this session?',
            'Which component would you like to see improved in future sessions?',
            'What specific improvements would you suggest for future sessions as per your previous selection?'
        ]
        
        # Check if required columns exist (at least User Name, Email Address, Topic)
        required_columns = ['User Name', 'Email Address', 'Topic']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({
                'success': False,
                'message': f'Missing required columns: {", ".join(missing_columns)}. Please ensure your Excel file has at least: User Name, Email Address, Topic.'
            })
        
        # Process ratings data
        processed_records = 0
        conn = get_db_connection()
        
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection error. Please try again later.'
            })
        
        try:
            cursor = conn.cursor()
            
            # Ensure ratings table exists with numeric columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT,
                    email_address TEXT,
                    submitted_date_and_time TEXT,
                    collected_from TEXT,
                    topic TEXT,
                    meeting_webinar_id TEXT,
                    satisfied_with_session_overall TEXT,
                    topics_clear_and_aligned TEXT,
                    professor_expertise_and_engagement TEXT,
                    slides_and_materials_enhanced_understanding TEXT,
                    key_insight_or_learning TEXT,
                    component_to_improve TEXT,
                    specific_improvements_suggested TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    satisfied_with_session_overall_numeric REAL,
                    topics_clear_and_aligned_numeric REAL,
                    professor_expertise_and_engagement_numeric REAL,
                    slides_and_materials_enhanced_understanding_numeric REAL,
                    average_rating REAL
                )
            ''')
            
            # Create indexes for better performance (only if they don't exist)
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ratings_email 
                ON ratings(email_address)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ratings_topic 
                ON ratings(topic)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ratings_meeting_id 
                ON ratings(meeting_webinar_id)
            ''')
            
            for index, row in df.iterrows():
                # Extract data from each row
                user_name = str(row.get('User Name', '')).strip()
                email_address = str(row.get('Email Address', '')).strip()
                topic = str(row.get('Topic', '')).strip()
                
                # Skip empty rows (must have at least name, email, and topic)
                if not user_name or not email_address or not topic:
                    continue
                
                # Extract all other columns with safe defaults
                submitted_date_time = str(row.get('Submitted Date and Time', '')).strip()
                collected_from = str(row.get('Collected from', '')).strip()
                meeting_webinar_id = str(row.get('Meeting/Webinar ID', '')).strip()
                
                # Rating questions (handle long column names)
                satisfied_overall = str(row.get('I am satisfied with the session overall.', '')).strip()
                topics_clear = str(row.get('The topics covered during this session were clear and aligned with the learning objectives.', '')).strip()
                professor_expertise = str(row.get('The professor demonstrated strong subject matter expertise, engaged learners, and addressed questions effectively.', '')).strip()
                slides_materials = str(row.get('The slides and reference materials presented during the session enhanced my understanding of the topic.', '')).strip()
                key_insight = str(row.get('What is one key insight or learning you will carry forward from this session?', '')).strip()
                component_improve = str(row.get('Which component would you like to see improved in future sessions?', '')).strip()
                specific_improvements = str(row.get('What specific improvements would you suggest for future sessions as per your previous selection?', '')).strip()
                
                # Check for existing duplicate records using email + name + date
                # Extract date from submitted_date_time if available
                rating_date = None
                if submitted_date_time:
                    try:
                        # Try to extract date from submitted_date_time
                        if len(submitted_date_time) >= 10:
                            rating_date = submitted_date_time[:10]  # Extract YYYY-MM-DD part
                    except:
                        rating_date = None
                
                if rating_date:
                    # Use email + name + date as unique identifier
                    cursor.execute('''
                        SELECT COUNT(*) FROM ratings 
                        WHERE email_address = ? AND user_name = ? AND DATE(submitted_date_and_time) = ?
                    ''', (email_address, user_name, rating_date))
                else:
                    # Fallback: Use email + name + topic
                    cursor.execute('''
                        SELECT COUNT(*) FROM ratings 
                        WHERE email_address = ? AND user_name = ? AND topic = ?
                    ''', (email_address, user_name, topic))
                
                duplicate_count = cursor.fetchone()[0]
                
                if duplicate_count > 0:
                    identifier = f"{user_name} - {email_address} - {rating_date or topic}"
                    print(f"⚠️ RATINGS: Skipping duplicate record for {identifier}")
                    continue  # Skip this record
                
                # Convert text ratings to numeric values
                satisfied_numeric, topics_numeric, professor_numeric, materials_numeric, average_rating = convert_ratings_to_numeric(
                    satisfied_overall, topics_clear, professor_expertise, slides_materials
                )
                
                # Insert ratings record (only if not duplicate)
                print(f"🔄 RATINGS: Inserting new record for {user_name} with numeric ratings: {average_rating}")
                cursor.execute('''
                    INSERT INTO ratings (
                        user_name, email_address, submitted_date_and_time, collected_from, topic,
                        meeting_webinar_id, satisfied_with_session_overall, topics_clear_and_aligned,
                        professor_expertise_and_engagement, slides_and_materials_enhanced_understanding,
                        key_insight_or_learning, component_to_improve, specific_improvements_suggested,
                        satisfied_with_session_overall_numeric, topics_clear_and_aligned_numeric,
                        professor_expertise_and_engagement_numeric, slides_and_materials_enhanced_understanding_numeric,
                        average_rating
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_name, email_address, submitted_date_time, collected_from, topic,
                    meeting_webinar_id, satisfied_overall, topics_clear, professor_expertise,
                    slides_materials, key_insight, component_improve, specific_improvements,
                    satisfied_numeric, topics_numeric, professor_numeric, materials_numeric, average_rating
                ))
                
                processed_records += 1
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Successfully processed {processed_records} new ratings records from your Excel file. Duplicate records were automatically skipped. Data has been appended to the ratings table.'
            })
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Error processing ratings data: {str(e)}. Please check your data format and try again.'
            })
    
    except Exception as e:
        print(f"❌ RATINGS UPLOAD: Main exception: {str(e)}")
        import traceback
        print(f"❌ RATINGS UPLOAD: Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}. Please try again.'
        })


@app.route('/admin/cleanup-attendance-tables', methods=['GET', 'POST'])
@login_required
def cleanup_attendance_tables():
    """Clean up old attendance tables - Admin only"""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'})
        
        cursor = conn.cursor()
        
        # Check if tables exist first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('attendance_uploads', 'attendance_records')")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # Drop old tables
        cursor.execute('DROP TABLE IF EXISTS attendance_uploads')
        cursor.execute('DROP TABLE IF EXISTS attendance_records')
        
        conn.commit()
        conn.close()
        
        if existing_tables:
            message = f'Deleted old attendance tables: {", ".join(existing_tables)}'
        else:
            message = 'No old attendance tables found to delete.'
        
        return jsonify({
            'success': True, 
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error cleaning up tables: {str(e)}'
        })


def update_live_session_attendance(conn, processed_records):
    """Update Live Session table with attendance statistics from uploaded data"""
    try:
        cursor = conn.cursor()
        
        # Get attendance statistics from uploaded data
        cursor.execute('''
            SELECT 
                session_id,
                COUNT(*) as total_attendees,
                SUM(CASE WHEN attended = 1 THEN 1 ELSE 0 END) as present_count,
                AVG(time_in_session) as avg_time,
                AVG(attendance_percentage) as avg_attendance_rate
            FROM attendance 
            WHERE source = 'upload'
            GROUP BY session_id
        ''')
        
        attendance_stats = cursor.fetchall()
        
        # Update Live Session table with calculated statistics
        for stats in attendance_stats:
            session_id, total, present, avg_time, avg_rate = stats
            
            # Try to match with existing Live Session records and update
            cursor.execute('''
                UPDATE [Live Session] 
                SET 
                    [Peak Attendance #] = ?,
                    [Unique attendees #] = ?,
                    [Avg. Rating #] = COALESCE([Avg. Rating #], 4.0)
                WHERE [Topic] LIKE ? OR [SME_Prof_Name] LIKE ?
            ''', (present, total, f'%{session_id}%', f'%{session_id}%'))
        
        conn.commit()
        print(f"Updated Live Session table with attendance data for {len(attendance_stats)} sessions")
        
    except Exception as e:
        print(f"Error updating Live Session table: {e}")
        # Don't raise exception as this is optional enhancement




@app.route('/dissertation')
@login_required
def dissertation():
    """Dissertation progress tracking page with real database data"""
    try:
        print("🔍 DISSERTATION: Starting dissertation route")
        
        # Import dissertation analytics
        from utils.dissertation_analytics import get_dissertation_analytics, get_dissertation_students_list
        
        # Get filter parameters
        cohort_filter = request.args.getlist('cohort')
        milestone_filter = request.args.getlist('milestone')
        status_filter = request.args.getlist('status')
        search_query = request.args.get('search', '').strip()
        page = max(1, request.args.get('page', 1, type=int))
        per_page = request.args.get('per_page', 10, type=int)
        
        # Validate per_page parameter
        allowed_per_page = [10, 25, 50, 100]
        if per_page not in allowed_per_page:
            per_page = 10
        
        print(f"🔍 DISSERTATION: Parsed params - page: {page}, per_page: {per_page}, cohorts: {cohort_filter}, milestones: {milestone_filter}, statuses: {status_filter}, search: '{search_query}'")
        
        # Get dissertation analytics
        dissertation_analytics = get_dissertation_analytics(cohort_filter if cohort_filter else None)
        
        # Get detailed student list with pagination
        students_data = get_dissertation_students_list(
            cohort_filter=cohort_filter if cohort_filter else None,
            milestone_filter=milestone_filter if milestone_filter else None,
            status_filter=status_filter if status_filter else None,
            search_filter=search_query if search_query else None,
            page=page,
            per_page=per_page
        )
        
        print(f"📊 DISSERTATION: Found {dissertation_analytics['total_dissertation']} dissertation students")
        print(f"📊 DISSERTATION: {dissertation_analytics['completed_count']} completed students")
        print(f"📊 DISSERTATION: Paginated result: {len(students_data.get('students', []))} students on page {page}")
        
        return render_template('dissertation.html', 
                             dissertation_analytics=dissertation_analytics,
                             students_list=students_data.get('students', []),
                             pagination=students_data.get('pagination', {}),
                             cohorts=dissertation_analytics.get('cohorts', []),
                             selected_cohorts=cohort_filter,
                             selected_milestones=milestone_filter,
                             selected_statuses=status_filter,
                             search_query=search_query,
                             last_updated=dissertation_analytics.get('last_updated'))
                             
    except Exception as e:
        print(f"❌ DISSERTATION ERROR: {str(e)}")
        import traceback
        print(f"❌ DISSERTATION TRACEBACK: {traceback.format_exc()}")
        flash('Error loading dissertation data', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/dissertation/filter', methods=['POST'])
@login_required
def filter_dissertation():
    """API endpoint for filtering dissertation data"""
    try:
        from utils.dissertation_analytics import get_dissertation_analytics, get_dissertation_students_list
        
        data = request.get_json()
        cohort_filter = data.get('cohorts', [])
        status_filter = data.get('status')
        
        # Get filtered analytics
        analytics = get_dissertation_analytics(cohort_filter if cohort_filter else None)
        students = get_dissertation_students_list(
            cohort_filter if cohort_filter else None, 
            status_filter
        )
        
        return jsonify({
            'success': True,
            'analytics': analytics,
            'students': students
        })
        
    except Exception as e:
        print(f"Error filtering dissertation data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dissertation/students')
@login_required
def get_dissertation_students_api():
    """API endpoint to get dissertation students list"""
    try:
        from utils.dissertation_analytics import get_dissertation_students_list
        
        cohort_filter = request.args.getlist('cohort')
        status_filter = request.args.get('status')
        
        students = get_dissertation_students_list(
            cohort_filter if cohort_filter else None,
            status_filter
        )
        
        return jsonify({
            'success': True,
            'students': students,
            'total': len(students)
        })
        
    except Exception as e:
        print(f"Error getting dissertation students: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Health check endpoint for hosting platforms
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring services"""
    return jsonify({
        'status': 'healthy',
        'service': 'EduOps360',
        'version': '14.0'
    }), 200

if __name__ == '__main__':
    import os
    import logging
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Test database connection on startup
        from utils.database import get_db_connection
        conn = get_db_connection()
        conn.close()
        logger.info("Database connection successful")
        
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_ENV') == 'development'
        logger.info(f"Starting app on port {port}, debug={debug}")
        app.run(host='0.0.0.0', port=port, debug=debug)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        raise
