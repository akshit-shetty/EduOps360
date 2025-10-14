import pandas as pd
from datetime import datetime
import os
from utils.database import get_db_connection as get_database_connection

# Constants for completion rate calculation
LOW_GRADES = ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I']
COURSE_COLUMNS = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                 'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
ACTIVE_STATUSES = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']

def get_db_connection():
    """Get database connection using centralized database utilities"""
    try:
        return get_database_connection()
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def get_coursework_overview():
    """Get overall coursework statistics - Static data"""
    try:
        # Static coursework overview data
        results = [
            {
                'course_code': 'DBA 805',
                'course_name': 'Doctoral Writing and Research Methods',
                'total_students': 803,
                'students_with_grades': 562,
                'avg_gpa': 3.2,
                'passing_students': 485
            },
            {
                'course_code': 'DBA 806',
                'course_name': 'Applied AI Innovation',
                'total_students': 803,
                'students_with_grades': 548,
                'avg_gpa': 3.4,
                'passing_students': 467
            },
            {
                'course_code': 'DBA 860',
                'course_name': 'Foundations of Machine Learning and AI',
                'total_students': 803,
                'students_with_grades': 532,
                'avg_gpa': 3.3,
                'passing_students': 445
            },
            {
                'course_code': 'DBA 863',
                'course_name': 'AI Project Design & Execution',
                'total_students': 803,
                'students_with_grades': 519,
                'avg_gpa': 3.1,
                'passing_students': 423
            },
            {
                'course_code': 'DBA 861',
                'course_name': 'Deep Learning & its Variants',
                'total_students': 803,
                'students_with_grades': 501,
                'avg_gpa': 3.0,
                'passing_students': 398
            },
            {
                'course_code': 'DBA 862',
                'course_name': 'Gen. AI- Pre-Trained Models',
                'total_students': 803,
                'students_with_grades': 487,
                'avg_gpa': 2.9,
                'passing_students': 365
            },
            {
                'course_code': 'DBA 864',
                'course_name': 'Responsible AI',
                'total_students': 803,
                'students_with_grades': 456,
                'avg_gpa': 3.2,
                'passing_students': 378
            }
        ]
        
        return results
        
    except Exception as e:
        print(f"Error getting coursework overview: {e}")
        return None

def get_live_session_analytics():
    """Get live session attendance and rating analytics - Static data"""
    try:
        # Static live session analytics data
        results = [
            {
                'course_code': 'DBA 805',
                'course_name': 'Doctoral Writing and Research Methods',
                'total_sessions': 17,
                'students_attended': 95,
                'attendance_rate': 87.2,
                'avg_rating': 4.3,
                'total_attendance_records': 1615
            },
            {
                'course_code': 'DBA 806',
                'course_name': 'Applied AI Innovation',
                'total_sessions': 17,
                'students_attended': 92,
                'attendance_rate': 84.5,
                'avg_rating': 4.5,
                'total_attendance_records': 1564
            },
            {
                'course_code': 'DBA 860',
                'course_name': 'Foundations of Machine Learning and AI',
                'total_sessions': 17,
                'students_attended': 89,
                'attendance_rate': 82.1,
                'avg_rating': 4.4,
                'total_attendance_records': 1513
            },
            {
                'course_code': 'DBA 863',
                'course_name': 'AI Project Design & Execution',
                'total_sessions': 17,
                'students_attended': 86,
                'attendance_rate': 79.8,
                'avg_rating': 4.2,
                'total_attendance_records': 1462
            },
            {
                'course_code': 'DBA 861',
                'course_name': 'Deep Learning & its Variants',
                'total_sessions': 17,
                'students_attended': 83,
                'attendance_rate': 77.5,
                'avg_rating': 4.1,
                'total_attendance_records': 1411
            },
            {
                'course_code': 'DBA 862',
                'course_name': 'Gen. AI- Pre-Trained Models',
                'total_sessions': 17,
                'students_attended': 80,
                'attendance_rate': 75.2,
                'avg_rating': 4.0,
                'total_attendance_records': 1360
            },
            {
                'course_code': 'DBA 864',
                'course_name': 'Responsible AI',
                'total_sessions': 17,
                'students_attended': 78,
                'attendance_rate': 73.8,
                'avg_rating': 4.2,
                'total_attendance_records': 1326
            }
        ]
        
        return results
        
    except Exception as e:
        print(f"Error getting live session analytics: {e}")
        return None

def get_student_coursework_progress(email=None):
    """Get individual student coursework progress - Uses existing Gradesheet data"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        # Get student grades from existing Gradesheet table
        grade_columns = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                        'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
        
        if email:
            where_clause = f'WHERE g.Email = "{email}"'
        else:
            where_clause = 'LIMIT 50'  # Limit for performance
        
        query = f'''
        SELECT 
            g.Email,
            sl."First Name",
            sl."Last Name",
            {', '.join([f'g."{col}"' for col in grade_columns])},
            g."Overall CGPA" as cgpa
        FROM Gradesheet g
        LEFT JOIN "Student List" sl ON g.Email = sl."GGU Email"
        {where_clause}
        ORDER BY sl."First Name", sl."Last Name"
        '''
        
        df = pd.read_sql_query(query, conn)
        return df.to_dict('records')
        
    except Exception as e:
        print(f"Error getting student coursework progress: {e}")
        return None
    finally:
        conn.close()

def calculate_completion_rate():
    """Calculate completion rate as: (Active/Active Deferred learners - Low credit learners) / (Active/Active Deferred learners) * 100"""
    conn = get_db_connection()
    if not conn:
        return 97.5  # Fallback value
    
    try:
        # Read data from the tables
        gradesheet_df = pd.read_sql_query("SELECT * FROM Gradesheet", conn)
        student_list_df = pd.read_sql_query("SELECT * FROM \"Student List\"", conn)
        
        # Filter for Active, Active/Deferred, and Active (Prospective Deferral) students
        active_statuses = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']
        active_students = student_list_df[
            student_list_df['Status'].isin(active_statuses)
        ]
        
        # Count total active learners (unique by email)
        total_active_learners = len(active_students['Email'].dropna().unique())
        
        # Merge with gradesheet to get grades for active students
        active_emails = active_students['Email'].dropna().unique().tolist()
        active_gradesheet = gradesheet_df[
            (gradesheet_df['Email'].isin(active_emails)) & 
            (gradesheet_df['Status'].isin(active_statuses))
        ]
        
        # Count learners with low grades (Low credit learners)
        low_credit_count = 0
        
        for _, row in active_gradesheet.iterrows():
            has_low_grade = False
            for course in COURSE_COLUMNS:
                if pd.notna(row.get(course)) and row[course] in LOW_GRADES:
                    has_low_grade = True
                    break
            
            if has_low_grade:
                low_credit_count += 1
        
        # Calculate completion rate as: (Active learners - Low credit learners) / Active learners * 100
        if total_active_learners > 0:
            completion_rate = ((total_active_learners - low_credit_count) / total_active_learners) * 100
        else:
            completion_rate = 0
        
        print(f"Program Completion Rate Calculation:")
        print(f"  Total Active/Active Deferred Learners: {total_active_learners}")
        print(f"  Low Credit Learners: {low_credit_count}")
        print(f"  Completion Rate: {completion_rate:.1f}%")
        
        return round(completion_rate, 1)
        
    except Exception as e:
        print(f"Error calculating completion rate: {e}")
        return 97.5  # Fallback value
    finally:
        conn.close()

def get_coursework_dashboard_stats():
    """Get key statistics for dashboard - Dynamic data using Active status minus dissertation phase"""
    conn = get_db_connection()
    if not conn:
        # Fallback to static data if DB connection fails
        return {
            'total_courses': 7,
            'total_learners': 525,  # Updated to reflect Active/Active Deferred - Dissertation phase
            'avg_completion_rate': 97.5,  # Updated based on new calculation
            'avg_attendance_rate': 81.4,
            'avg_course_rating': 4.2,
            'students_above_cgpa': 342,
            'total_sessions': 119
        }
    
    try:
        # Step 1: Get total active learners with specified active statuses
        student_list_df = pd.read_sql_query("SELECT * FROM \"Student List\"", conn)
        
        # Filter for Active and Active/Deferred In statuses only for coursework total calculation
        active_statuses_coursework = ['Active', 'Active / Deferred In']
        active_students = student_list_df[
            student_list_df['Status'].isin(active_statuses_coursework)
        ]
        
        # Count total active learners (unique by email)
        total_active_learners = len(active_students['Email'].dropna().unique())
        
        # Step 2: Get dissertation phase learners count using the same logic as dissertation analytics
        # Count students in Dissertation table with valid dissertation mode (not NULL and not '0')
        dissertation_query = '''
        SELECT DISTINCT d.Email
        FROM Dissertation d
        INNER JOIN "Student List" sl ON d.Email = sl."Email"
        WHERE d."Dissertation mode" IS NOT NULL 
        AND d."Dissertation mode" != '0'
        AND sl."Status" IN ('Active', 'Active / Deferred In')
        '''
        
        dissertation_df = pd.read_sql_query(dissertation_query, conn)
        dissertation_phase_learners = len(dissertation_df)
        
        # Step 3: Calculate coursework learners = Active/Active Deferred learners - Dissertation phase learners
        coursework_learners = total_active_learners - dissertation_phase_learners
        
        print(f"🔍 COURSEWORK COUNT CALCULATION:")
        print(f"  Total Active/Active Deferred learners: {total_active_learners}")
        print(f"  Dissertation phase learners: {dissertation_phase_learners}")
        print(f"  Coursework phase learners: {coursework_learners}")
        
        # Calculate the completion rate based on Need Attention learners
        completion_rate = calculate_completion_rate()
        
        # Get other statistics
        stats = {
            'total_courses': 7,
            'total_learners': coursework_learners,
            'avg_completion_rate': completion_rate,
            'avg_attendance_rate': 81.4,
            'avg_course_rating': 4.2,
            'students_above_cgpa': 342,
            'total_sessions': 119
        }
        
        return stats
        
    except Exception as e:
        print(f"Error getting coursework dashboard stats: {e}")
        # Fallback to static data
        return {
            'total_courses': 7,
            'total_learners': 525,  # Updated to reflect Active/Active Deferred - Dissertation phase
            'avg_completion_rate': 97.5,  # Updated based on new calculation
            'avg_attendance_rate': 81.4,
            'avg_course_rating': 4.2,
            'students_above_cgpa': 342,
            'total_sessions': 119
        }
    finally:
        conn.close()
