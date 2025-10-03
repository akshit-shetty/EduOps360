from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
import sqlite3
import pandas as pd
from pathlib import Path
import json
import os
import subprocess
import tempfile
import datetime
import hashlib
import secrets
from functools import wraps
from document_and_email import document_bp
from reminder import reminders_bp
from create_folders import folders_bp
from chatbot import chatbot_bp
import sys
print("Python version:", sys.version)
app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'  # Make sure this is set
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)
# Constants
DB_PATH = os.environ.get('DATABASE_URL', 'GGU DBA ET Learner Journey.db').replace('sqlite:///', '')

LOW_GRADES = ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I']
COURSE_COLUMNS = ['DBA 805 Grade', 'DBA 806 Grade', 'DBA 863 Grade', 
                 'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
ACTIVE_STATUSES = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']

# Authentication functions
def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(email, password):
    """Verify user credentials"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, email, role, password_hash, first_name, last_name FROM users 
            WHERE email = ? AND is_active = TRUE
        ''', (email,))
        
        user = cursor.fetchone()
        if user:
            user_id, user_email, role, stored_hash, first_name, last_name = user
            if hash_password(password) == stored_hash:
                return {
                    'id': user_id,
                    'email': user_email,
                    'role': role,
                    'first_name': first_name or '',
                    'last_name': last_name or ''
                }
    except Exception as e:
        print(f"Error verifying user: {e}")
    finally:
        conn.close()
    
    return None

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
        if 'user_id' not in session:  # Fixed: session instead of session
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':  # Fixed: session instead of session
            return "Unauthorized - Admin access required", 403
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin panel for user management"""
    conn = get_db_connection()
    if not conn:
        flash('Error connecting to database', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Get all users
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, first_name, last_name, email, role, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC
        ''')
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
                'created_at': user[6]
            })
        
        return render_template('admin_users.html', 
                             users=users_list,
                             last_updated=get_last_updated_time())
        
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        flash('Error loading admin panel', 'error')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

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
    
    conn = get_db_connection()
    if not conn:
        flash('Error connecting to database', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET first_name = ?, last_name = ?, password_hash = ?, role = ?, is_active = TRUE
                WHERE email = ?
            ''', (first_name, last_name, password_hash, role, email))
            flash(f'User {email} updated successfully!', 'success')
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (first_name, last_name, email, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (first_name, last_name, email, password_hash, role))
            flash(f'User {email} created successfully! Password: {password}', 'success')
        
        conn.commit()
        
    except Exception as e:
        print(f"Error adding user: {e}")
        flash(f'Error creating user: {str(e)}', 'error')
    finally:
        conn.close()
    
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

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def get_last_updated_time():
    """Get the last modified time of the database file"""
    try:
        if os.path.exists(DB_PATH):
            mod_time = os.path.getmtime(DB_PATH)
            return datetime.datetime.fromtimestamp(mod_time)
    except:
        pass
    return datetime.datetime.now()

def get_data_last_updated():
    """Get the last updated time for data (alias for get_last_updated_time)"""
    return get_last_updated_time()

def apply_filters(df, cohort_filter=None, slot_filter=None, status_filter=None, country_filter=None):
    """Apply filters to dataframe - now handles multiple values"""
    if cohort_filter:
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
    
    if slot_filter:
        if not isinstance(slot_filter, list):
            slot_filter = [slot_filter]
        # Handle slot filtering (first 6 characters)
        slot_filter = [slot[:6] for slot in slot_filter if slot]
        df = df[df['Slot'].str[:6].isin(slot_filter)]
    
    if status_filter:
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
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1,
                'next_num': page + 1
            }
        }
        
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return None
    finally:
        conn.close()


# In the get_all_learners_data function, remove country_filter parameter and usage
def get_all_learners_data(cohort_filter=None, slot_filter=None, status_filter=None, search_filter=None, page=1, per_page=20):
    """Get data for all learners page - MODIFIED to keep duplicates"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Read data
        student_list_df = pd.read_sql_query("SELECT * FROM \"Student List\"", conn)
        gradesheet_df = pd.read_sql_query("SELECT * FROM Gradesheet", conn)
        
        # Start with all data
        working_df = student_list_df.copy()
        
        # Apply filters
        working_df = apply_filters(working_df, cohort_filter, slot_filter, status_filter)
        
        # Search - apply search to ALL columns including all data
        if search_filter:
            search_filter = search_filter.lower()
            mask = (
                working_df['First Name'].str.lower().str.contains(search_filter, na=False) |
                working_df['Last Name'].str.lower().str.contains(search_filter, na=False) |
                working_df['Email'].str.lower().str.contains(search_filter, na=False) |
                working_df['Cohort #'].astype(str).str.contains(search_filter, na=False) |
                working_df['Slot'].astype(str).str.contains(search_filter, na=False) |
                working_df['Batch'].str.lower().str.contains(search_filter, na=False) |
                working_df['Status'].str.lower().str.contains(search_filter, na=False) |
                working_df['User ID'].astype(str).str.contains(search_filter, na=False)  # Add User ID to search
            )
            working_df = working_df[mask]
        
        # Build filter lists from full dataset (not filtered)
        cohorts = sorted(student_list_df['Cohort #'].dropna().unique())
        slots = sorted(student_list_df['Slot'].dropna().str.slice(0, 6).unique())
        statuses = sorted(student_list_df['Status'].dropna().unique())
        
        # NO DEDUPLICATION - Keep all rows
        # Counts - counting all rows including duplicates
        total_learners = len(working_df)  # This includes all matching rows
        active_statuses = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']
        active_learners_count = len(working_df[working_df['Status'].isin(active_statuses)])
        
        # For dissertation phase count, merge with gradesheet but preserve all rows
        merged_for_count = working_df.merge(
            gradesheet_df[['Email', 'Cohort #', 'Courses Completed', 'Courses Incomplete']],
            on=['Email', 'Cohort #'],
            how='left'
        )
        # Remove any potential duplicates from the merge
        merged_for_count = merged_for_count.drop_duplicates(subset=['Email', 'Cohort #', 'First Name', 'Last Name'])
        
        merged_for_count['Courses Completed'] = merged_for_count['Courses Completed'].fillna(0).astype(int)
        merged_for_count['Courses Incomplete'] = merged_for_count['Courses Incomplete'].fillna(0).astype(int)
        merged_for_count['Net Completed'] = merged_for_count['Courses Completed'] - merged_for_count['Courses Incomplete']
        
        dissertation_phase_count = len(merged_for_count[merged_for_count['Net Completed'] == 7])
        
        # Pagination
        total_pages = (total_learners + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_df = working_df.iloc[start_idx:end_idx]
        
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
                'total_learners': total_learners,  # All rows including duplicates
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1,
                'next_num': page + 1
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
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:  # Fixed: session instead of session
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = verify_user(email, password)
        if user:
            session['user_id'] = user['id']  # Fixed: session instead of session
            session['user_email'] = user['email']  # Fixed: session instead of session
            session['role'] = user['role']  # Fixed: session instead of session
            session['first_name'] = user.get('first_name', '')  # Fixed: session instead of session
            session['last_name'] = user.get('last_name', '')  # Fixed: session instead of session
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Changed from session to session
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
    cohort_filter = request.args.getlist('cohort')
    slot_filter = request.args.getlist('slot')
    status_filter = request.args.getlist('status')
    search_filter = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    
    data = get_dashboard_data(cohort_filter, slot_filter, status_filter, search_filter, page)
    if not data:
        return "Error loading data", 500
    
    # Add selected filters to template context
    data['selected_cohorts'] = cohort_filter
    data['selected_slots'] = slot_filter
    data['selected_statuses'] = status_filter
    data['last_updated'] = get_last_updated_time()  # Add this line
    
    flash_messages = []
        
    return render_template('dashboard.html', **data)

# In the learners route, remove country filter handling
@app.route('/learners')
@login_required
def learners():
    try:
        # Get filter parameters with multi-select support
        selected_cohorts = request.args.getlist('cohort')
        selected_slots = request.args.getlist('slot')
        selected_statuses = request.args.getlist('status')
        # Remove country filter
        search_query = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)

        # Use the existing function to get learners data (remove country_filter)
        data = get_all_learners_data(
            cohort_filter=selected_cohorts,
            slot_filter=selected_slots, 
            status_filter=selected_statuses,
            search_filter=search_query,
            page=page,
            per_page=10
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
                    'per_page': 10, 
                    'total': 0, 
                    'pages': 0,
                    'has_prev': False,
                    'has_next': False,
                    'prev_num': 0,
                    'next_num': 0
                }
            }

        # Add selected filters and last updated time (remove country)
        data['selected_cohorts'] = selected_cohorts
        data['selected_slots'] = selected_slots
        data['selected_statuses'] = selected_statuses
        data['last_updated'] = get_last_updated_time()

        return render_template('learners.html', **data)

    except Exception as e:
        flash(f'Error loading learners data: {str(e)}', 'error')
        # Return empty data structure on error
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
                                'prev_num': 0,
                                'next_num': 0
                            },
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
        import traceback
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
                course_columns = ['DBA 805 Grade', 'DBA 806 Grade', 'DBA 863 Grade', 
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
        import traceback
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
        
    return jsonify(data)

app.register_blueprint(document_bp, url_prefix="/document")
app.register_blueprint(reminders_bp, url_prefix="/reminder")
app.register_blueprint(folders_bp, url_prefix="/folders")
app.register_blueprint(chatbot_bp)


@app.route("/automation-tools")
@login_required
def automation_tools():
    return render_template("automation_tools.html")

# Add these route handlers for direct access to pages
@app.route("/document")
@login_required
def document_home():
    return render_template("document_creation.html")

@app.route("/reminder")
@login_required
def reminder_home():
    return render_template("reminder.html")

@app.route("/folders")
@login_required
def folder_home():
    return render_template("folder_creator_ui.html")


if __name__ == '__main__':

    app.run(debug=True)
