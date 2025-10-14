"""
Dissertation Analytics Module for EduOps360
Handles all dissertation-related data processing and analytics
"""

import sqlite3
import pandas as pd
from datetime import datetime
import traceback

def get_db_connection():
    """Get database connection"""
    try:
        conn = sqlite3.connect('eduops360.db')
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def get_milestone_breakdown(df, submission_col, approval_col, total_students):
    """
    Calculate milestone breakdown for a specific milestone
    
    Args:
        df: DataFrame with dissertation data
        submission_col: Column name for submission status
        approval_col: Column name for approval status (can be None for IRB)
        total_students: Total number of dissertation students
    
    Returns:
        Dictionary with breakdown statistics
    """
    if df.empty:
        return {
            'submitted': {'count': 0, 'percent': 0},
            'not_submitted': {'count': 0, 'percent': 0},
            'approved': {'count': 0, 'percent': 0},
            'not_approved': {'count': 0, 'percent': 0}
        }
    
    # Count submissions
    submitted_count = len(df[df[submission_col] == 'Submitted']) if submission_col in df.columns else 0
    
    # Count explicit "Not Submitted" values only (including typo "Not Submited")
    if submission_col in df.columns:
        not_submitted_mask = (
            (df[submission_col] == 'Not Submitted') |
            (df[submission_col] == 'Not Submited')  # Handle typo
        )
        not_submitted_count = len(df[not_submitted_mask])
    else:
        not_submitted_count = 0
    
    # Count approvals
    if approval_col and approval_col in df.columns:
        approved_count = len(df[df[approval_col] == 'Approved'])
        not_approved_count = len(df[df[approval_col] == 'Not Approved'])
    else:
        # For IRB, use the IRB column directly
        if submission_col == 'IRB':
            approved_count = len(df[df[submission_col] == 'Approved'])
            not_approved_count = len(df[df[submission_col] == 'Not Approved'])
        else:
            approved_count = 0
            not_approved_count = 0
    
    return {
        'submitted': {
            'count': submitted_count,
            'percent': round((submitted_count / total_students) * 100, 1) if total_students > 0 else 0
        },
        'not_submitted': {
            'count': not_submitted_count,
            'percent': round((not_submitted_count / total_students) * 100, 1) if total_students > 0 else 0
        },
        'approved': {
            'count': approved_count,
            'percent': round((approved_count / total_students) * 100, 1) if total_students > 0 else 0
        },
        'not_approved': {
            'count': not_approved_count,
            'percent': round((not_approved_count / total_students) * 100, 1) if total_students > 0 else 0
        }
    }

def get_dissertation_students():
    """
    Get all students who are in dissertation phase (have valid Dissertation mode in Dissertation table)
    
    Returns:
        DataFrame with dissertation students data
    """
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        # Count students in Dissertation table with valid dissertation mode (not NULL and not '0')
        query = '''
        SELECT d.Email, d."Learner Name", d."Cohort #", 
               d."Dissertation mode", d."Grading Status", d.Chair, d."Co-Chair"
        FROM Dissertation d
        WHERE d."Dissertation mode" IS NOT NULL 
        AND d."Dissertation mode" != '0'
        '''
        
        df = pd.read_sql_query(query, conn)
        print(f"Found {len(df)} students in dissertation phase with valid Dissertation mode")
        return df
        
    except Exception as e:
        print(f"Error getting dissertation students: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_dissertation_analytics(cohort_filter=None):
    """
    Get comprehensive dissertation analytics
    
    Args:
        cohort_filter: Optional cohort filter (string or list)
    
    Returns:
        Dictionary with dissertation analytics
    """
    conn = get_db_connection()
    if not conn:
        return get_default_dissertation_data()
    
    try:
        print("🔍 Getting dissertation analytics...")
        
        # Get dissertation students (those with 7 completed courses)
        dissertation_students_df = get_dissertation_students()
        
        if dissertation_students_df.empty:
            print("No dissertation students found")
            return get_default_dissertation_data()
        
        # Apply cohort filter if provided
        if cohort_filter:
            if isinstance(cohort_filter, str):
                cohort_filter = [cohort_filter]
            dissertation_students_df = dissertation_students_df[
                dissertation_students_df['Cohort #'].isin(cohort_filter)
            ]
        
        total_dissertation_students = len(dissertation_students_df)
        print(f"Total dissertation students: {total_dissertation_students}")
        
        # Get dissertation milestone data - use same filtering as table function
        dissertation_query = '''
        SELECT d.Email, d."Topic Proposal Submission", d."Topic Proposal Approval",
               d.IRB, d."IRB Approval", d."Research Proposal Submission", 
               d."Research Proposal Approval", d."Final Proposal Submission", 
               d."Final Proposal Approval"
        FROM Dissertation d
        WHERE d."Dissertation mode" IS NOT NULL 
        AND d."Dissertation mode" != '0'
        '''
        
        # Add cohort filter to dissertation query if needed
        if cohort_filter:
            placeholders = ','.join(['?' for _ in cohort_filter])
            dissertation_query += f' AND d."Cohort #" IN ({placeholders})'
            filtered_dissertation_df = pd.read_sql_query(dissertation_query, conn, params=cohort_filter)
        else:
            filtered_dissertation_df = pd.read_sql_query(dissertation_query, conn)
        
        print(f"Filtered dissertation records: {len(filtered_dissertation_df)}")
        
        # Update total count to match filtered data
        total_dissertation_students = len(filtered_dissertation_df)
        
        # Calculate milestone breakdowns
        topic_proposal_stats = get_milestone_breakdown(
            filtered_dissertation_df, 'Topic Proposal Submission', 'Topic Proposal Approval', 
            total_dissertation_students
        )
        
        irb_stats = get_milestone_breakdown(
            filtered_dissertation_df, 'IRB', 'IRB Approval', 
            total_dissertation_students
        )
        
        research_proposal_stats = get_milestone_breakdown(
            filtered_dissertation_df, 'Research Proposal Submission', 'Research Proposal Approval', 
            total_dissertation_students
        )
        
        final_defense_stats = get_milestone_breakdown(
            filtered_dissertation_df, 'Final Proposal Submission', 'Final Proposal Approval', 
            total_dissertation_students
        )
        
        # Calculate overall statistics
        total_approvals = (topic_proposal_stats['approved']['count'] + 
                          irb_stats['approved']['count'] + 
                          research_proposal_stats['approved']['count'] + 
                          final_defense_stats['approved']['count'])
        
        total_not_approved = (topic_proposal_stats['not_approved']['count'] + 
                             irb_stats['not_approved']['count'] + 
                             research_proposal_stats['not_approved']['count'] + 
                             final_defense_stats['not_approved']['count'])
        
        # Calculate completed students (all 4 milestones approved)
        completed_count = 0
        if not filtered_dissertation_df.empty:
            for _, row in filtered_dissertation_df.iterrows():
                milestones_approved = 0
                if row.get('Topic Proposal Approval') == 'Approved':
                    milestones_approved += 1
                if row.get('IRB Approval') == 'Approved' or row.get('IRB') == 'Approved':
                    milestones_approved += 1
                if row.get('Research Proposal Approval') == 'Approved':
                    milestones_approved += 1
                if row.get('Final Proposal Approval') == 'Approved':
                    milestones_approved += 1
                
                if milestones_approved == 4:
                    completed_count += 1
        
        # Calculate pending reviews
        total_submitted = (topic_proposal_stats['submitted']['count'] + 
                          irb_stats['submitted']['count'] + 
                          research_proposal_stats['submitted']['count'] + 
                          final_defense_stats['submitted']['count'])
        
        overall_pending_review = max(0, total_submitted - total_approvals - total_not_approved)
        
        # Get cohort list for filtering - only from dissertation students
        cohorts_query = '''
        SELECT DISTINCT d."Cohort #" 
        FROM Dissertation d 
        WHERE d."Dissertation mode" IS NOT NULL 
        AND d."Dissertation mode" != '0'
        AND d."Cohort #" IS NOT NULL 
        ORDER BY d."Cohort #"
        '''
        cohorts_df = pd.read_sql_query(cohorts_query, conn)
        cohorts = cohorts_df['Cohort #'].tolist()
        
        return {
            'total_dissertation': total_dissertation_students,
            'completed_count': completed_count,
            'total_approvals': total_approvals,
            'total_not_approved': total_not_approved,
            'overall_pending_review': overall_pending_review,
            'topic_proposal': topic_proposal_stats,
            'irb': irb_stats,
            'research_proposal': research_proposal_stats,
            'final_defense': final_defense_stats,
            'cohorts': cohorts,
            'last_updated': datetime.now()
        }
        
    except Exception as e:
        print(f"Error in get_dissertation_analytics: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return get_default_dissertation_data()
    finally:
        conn.close()

def get_default_dissertation_data():
    """Return default dissertation data structure when no data is available"""
    return {
        'total_dissertation': 0,
        'completed_count': 0,
        'total_approvals': 0,
        'total_not_approved': 0,
        'overall_pending_review': 0,
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
        'cohorts': [],
        'last_updated': None
    }

def get_dissertation_students_list(cohort_filter=None, milestone_filter=None, status_filter=None, search_filter=None, page=1, per_page=10):
    """
    Get detailed list of dissertation students with their progress and pagination
    
    Args:
        cohort_filter: Optional cohort filter
        milestone_filter: Optional milestone filter (list of milestone names)
        status_filter: Optional status filter (list of statuses)
        search_filter: Optional search query
        page: Page number (1-indexed)
        per_page: Number of items per page
    
    Returns:
        Dictionary with students list and pagination info
    """
    conn = get_db_connection()
    if not conn:
        return {
            'students': [],
            'pagination': {
                'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0,
                'has_prev': False, 'has_next': False, 'prev_num': None, 'next_num': None
            }
        }
    
    try:
        # Base query to get dissertation students with their milestone data
        query = '''
        SELECT 
            d.Email, d."Learner Name", d."Cohort #", 
            g."Overall CGPA", s.Status,
            d."Topic Proposal Submission", d."Topic Proposal Approval",
            d.IRB, d."IRB Approval", 
            d."Research Proposal Submission", d."Research Proposal Approval",
            d."Final Proposal Submission", d."Final Proposal Approval",
            d.Chair, d."Co-Chair", d."Dissertation mode"
        FROM Dissertation d
        LEFT JOIN Gradesheet g ON d.Email = g.Email AND d."Cohort #" = g."Cohort #"
        LEFT JOIN "Student List" s ON d.Email = s.Email AND d."Cohort #" = s."Cohort #"
        WHERE d."Dissertation mode" IS NOT NULL 
        AND d."Dissertation mode" != '0'
        '''
        
        params = []
        if cohort_filter:
            if isinstance(cohort_filter, str):
                cohort_filter = [cohort_filter]
            placeholders = ','.join(['?' for _ in cohort_filter])
            query += f' AND d."Cohort #" IN ({placeholders})'
            params.extend(cohort_filter)
        
        query += ' ORDER BY d."Cohort #", d."Learner Name"'
        
        df = pd.read_sql_query(query, conn, params=params)
        
        # Remove duplicates based on email and cohort
        df = df.drop_duplicates(subset=['Email', 'Cohort #'], keep='first')
        
        # Process all students first to get milestone details
        all_students = []
        for _, row in df.iterrows():
            # Calculate progress
            milestones_completed = 0
            milestone_details = []
            milestone_statuses = {}
            
            # Topic Proposal
            if row['Topic Proposal Approval'] == 'Approved':
                milestones_completed += 1
                milestone_details.append('Topic Proposal: Approved')
                milestone_statuses['Topic Proposal'] = 'Approved'
            elif row['Topic Proposal Approval'] == 'Not Approved':
                milestone_details.append('Topic Proposal: Not Approved')
                milestone_statuses['Topic Proposal'] = 'Not Approved'
            elif row['Topic Proposal Submission'] == 'Submitted':
                milestone_details.append('Topic Proposal: Submitted')
                milestone_statuses['Topic Proposal'] = 'Submitted'
            elif row['Topic Proposal Submission'] == 'Not Submitted':
                milestone_details.append('Topic Proposal: Not Submitted')
                milestone_statuses['Topic Proposal'] = 'Not Submitted'
            else:
                milestone_details.append('Topic Proposal: Pending')
                milestone_statuses['Topic Proposal'] = 'Pending'
            
            # IRB
            if row['IRB Approval'] == 'Approved' or row['IRB'] == 'Approved':
                milestones_completed += 1
                milestone_details.append('IRB: Approved')
                milestone_statuses['IRB'] = 'Approved'
            elif row['IRB Approval'] == 'Not Approved':
                milestone_details.append('IRB: Not Approved')
                milestone_statuses['IRB'] = 'Not Approved'
            elif row['IRB'] == 'Submitted':
                milestone_details.append('IRB: Submitted')
                milestone_statuses['IRB'] = 'Submitted'
            elif row['IRB'] == 'Not Submitted':
                milestone_details.append('IRB: Not Submitted')
                milestone_statuses['IRB'] = 'Not Submitted'
            else:
                milestone_details.append('IRB: Pending')
                milestone_statuses['IRB'] = 'Pending'
            
            # Research Proposal
            if row['Research Proposal Approval'] == 'Approved':
                milestones_completed += 1
                milestone_details.append('Research Proposal: Approved')
                milestone_statuses['Research Proposal'] = 'Approved'
            elif row['Research Proposal Approval'] == 'Not Approved':
                milestone_details.append('Research Proposal: Not Approved')
                milestone_statuses['Research Proposal'] = 'Not Approved'
            elif row['Research Proposal Submission'] == 'Submitted':
                milestone_details.append('Research Proposal: Submitted')
                milestone_statuses['Research Proposal'] = 'Submitted'
            elif row['Research Proposal Submission'] == 'Not Submitted':
                milestone_details.append('Research Proposal: Not Submitted')
                milestone_statuses['Research Proposal'] = 'Not Submitted'
            else:
                milestone_details.append('Research Proposal: Pending')
                milestone_statuses['Research Proposal'] = 'Pending'
            
            # Final Defense
            if row['Final Proposal Approval'] == 'Approved':
                milestones_completed += 1
                milestone_details.append('Final Defense: Approved')
                milestone_statuses['Final Defense'] = 'Approved'
            elif row['Final Proposal Approval'] == 'Not Approved':
                milestone_details.append('Final Defense: Not Approved')
                milestone_statuses['Final Defense'] = 'Not Approved'
            elif row['Final Proposal Submission'] == 'Submitted':
                milestone_details.append('Final Defense: Submitted')
                milestone_statuses['Final Defense'] = 'Submitted'
            elif row['Final Proposal Submission'] == 'Not Submitted':
                milestone_details.append('Final Defense: Not Submitted')
                milestone_statuses['Final Defense'] = 'Not Submitted'
            else:
                milestone_details.append('Final Defense: Pending')
                milestone_statuses['Final Defense'] = 'Pending'
            
            progress_percent = (milestones_completed / 4) * 100
            
            # Parse learner name into first and last name
            learner_name = row['Learner Name'] or ''
            name_parts = learner_name.split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            student = {
                'email': row['Email'],
                'first_name': first_name,
                'last_name': last_name,
                'full_name': learner_name,
                'cohort': row['Cohort #'],
                'cgpa': row['Overall CGPA'],
                'status': row['Status'],
                'chair': row['Chair'],
                'co_chair': row['Co-Chair'],
                'milestones_completed': milestones_completed,
                'progress_percent': progress_percent,
                'milestone_details': milestone_details,
                'milestone_statuses': milestone_statuses,
                'is_completed': milestones_completed == 4
            }
            all_students.append(student)
        
        # Apply filters
        filtered_students = all_students
        
        # Apply search filter
        if search_filter:
            search_lower = search_filter.lower()
            filtered_students = [
                student for student in filtered_students
                if (search_lower in student['full_name'].lower() or
                    search_lower in student['email'].lower() or
                    search_lower in str(student['cohort']).lower())
            ]
        
        # Apply milestone and status filters
        if milestone_filter or status_filter:
            def matches_filters(student):
                # Check if student has any milestone that matches both milestone and status filters
                for milestone_name, milestone_status in student['milestone_statuses'].items():
                    milestone_match = not milestone_filter or milestone_name in milestone_filter
                    status_match = not status_filter or milestone_status in status_filter
                    if milestone_match and status_match:
                        return True
                return False
            
            filtered_students = [student for student in filtered_students if matches_filters(student)]
        
        # Calculate pagination
        total_students = len(filtered_students)
        total_pages = max(1, (total_students + per_page - 1) // per_page) if total_students > 0 else 1
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_students = filtered_students[start_idx:end_idx]
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_students,
            'pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        
        return {
            'students': paginated_students,
            'pagination': pagination
        }
        
    except Exception as e:
        print(f"Error getting dissertation students list: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            'students': [],
            'pagination': {
                'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0,
                'has_prev': False, 'has_next': False, 'prev_num': None, 'next_num': None
            }
        }
    finally:
        conn.close()
