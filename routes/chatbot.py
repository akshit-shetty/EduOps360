# chatbot.py
from flask import Blueprint, request, jsonify, session as flask_session
import sqlite3
import pandas as pd
import logging
from typing import Dict, List, Any, Optional, Tuple
import re
from difflib import SequenceMatcher
from collections import defaultdict
from openai import OpenAI
import json
# Enhanced chatbot with intelligent query matching

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)

# Database path
DB_PATH = "eduops360.db"

class EduOpsChatbot:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
        # Initialize NVIDIA Qwen client with graceful fallback
        self.nvidia_client = None
        self.ai_available = False
        
        try:
            # Check if OpenAI is available and compatible
            import openai
            logger.info("OpenAI library found, attempting NVIDIA client initialization...")
            
            # Try new OpenAI client style first
            try:
                self.nvidia_client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key="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"
                )
                self.ai_available = True
                logger.info("✅ NVIDIA client initialized successfully (new style)")
            except Exception as e1:
                logger.warning(f"New style initialization failed: {e1}")
                
                # Try legacy style
                try:
                    openai.api_base = "https://integrate.api.nvidia.com/v1"
                    openai.api_key = "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"
                    self.nvidia_client = openai
                    self.ai_available = True
                    logger.info("✅ NVIDIA client initialized successfully (legacy style)")
                except Exception as e2:
                    logger.error(f"Legacy style initialization also failed: {e2}")
                    
        except ImportError:
            logger.warning("OpenAI library not available")
        except Exception as e:
            logger.error(f"Unexpected error during AI initialization: {e}")
        
        if not self.ai_available:
            logger.info("🤖 AI functionality disabled - chatbot will work with predefined patterns only")
        
        # Initialize query patterns for intelligent matching
        self.query_patterns = self._initialize_query_patterns()
        
        # Keywords for fuzzy matching
        self.keywords_mapping = self._initialize_keywords_mapping()
        
    def get_db_connection(self):
        """Create and return a database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def _initialize_query_patterns(self) -> List[Dict[str, Any]]:
        """Initialize comprehensive query patterns focused on program coordinator needs"""
        return [
            {
                'id': 1,
                'name': 'active_students_by_cohort',
                'patterns': [
                    'show all active students from cohort {cohort}',
                    'active students in cohort {cohort}',
                    'list active learners from {cohort}'
                ],
                'keywords': ['active', 'students', 'cohort', 'show', 'list'],
                'sql': "SELECT First_Name, Last_Name, Email, Cohort_#, Status FROM Student_List WHERE Status IN ('Active', 'Active / Deferred In') AND Cohort_# = '{cohort}'",
                'parameters': ['cohort'],
                'description': 'Show all active students from a specific cohort'
            },
            {
                'id': 2,
                'name': 'find_learner_by_email',
                'patterns': [
                    'get student details using email {email}',
                    'find learner by email {email}',
                    'student with email {email}'
                ],
                'keywords': ['student', 'details', 'email', 'find', 'learner'],
                'sql': "SELECT * FROM Student_List WHERE Email = '{email}'",
                'parameters': ['email'],
                'description': 'Find learner details by email address'
            },
            {
                'id': 3,
                'name': 'total_enrollment_summary',
                'patterns': [
                    'total unique learners',
                    'how many students enrolled',
                    'total enrollment count',
                    'give me enrollment numbers'
                ],
                'keywords': ['total', 'unique', 'learners', 'enrollment', 'count'],
                'sql': "SELECT COUNT(DISTINCT Email) as Total_Students FROM Student_List",
                'parameters': [],
                'description': 'Get total enrollment count'
            },
            {
                'id': 4,
                'name': 'active_vs_inactive_breakdown',
                'patterns': [
                    'active vs inactive student breakdown',
                    'student status distribution',
                    'enrollment status summary',
                    'how many active students'
                ],
                'keywords': ['active', 'inactive', 'status', 'breakdown', 'distribution'],
                'sql': "SELECT Status, COUNT(*) AS Student_Count FROM Student_List GROUP BY Status ORDER BY Student_Count DESC",
                'parameters': [],
                'description': 'Show student distribution by enrollment status'
            },
            {
                'id': 5,
                'name': 'cohort_enrollment_numbers',
                'patterns': [
                    'students per cohort',
                    'cohort enrollment numbers',
                    'how many in each cohort',
                    'cohort size breakdown',
                    'show cohort statistics',
                    'cohort statistics',
                    'cohort stats'
                ],
                'keywords': ['cohort', 'enrollment', 'numbers', 'size', 'students', 'statistics', 'stats'],
                'sql': "SELECT Cohort_#, COUNT(*) AS Total_Students, SUM(CASE WHEN Status IN ('Active', 'Active / Deferred In') THEN 1 ELSE 0 END) AS Active_Students FROM Student_List GROUP BY Cohort_# ORDER BY Cohort_#",
                'parameters': [],
                'description': 'Show enrollment numbers by cohort'
            },
            {
                'id': 6,
                'name': 'students_at_academic_risk',
                'patterns': [
                    'students at academic risk',
                    'learners needing intervention',
                    'at-risk students list',
                    'academic support needed'
                ],
                'keywords': ['risk', 'intervention', 'support', 'academic', 'students'],
                'sql': "SELECT s.First_Name, s.Last_Name, s.Cohort_#, g.Overall_CGPA, g.Courses_Incomplete FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email WHERE (g.Overall_CGPA < 3.0 OR g.Courses_Incomplete > 1) AND s.Status IN ('Active', 'Active / Deferred In') ORDER BY g.Overall_CGPA ASC",
                'parameters': [],
                'description': 'Identify students who need academic intervention'
            },
            {
                'id': 7,
                'name': 'graduation_eligible_students',
                'patterns': [
                    'students ready for graduation',
                    'graduation eligible students',
                    'who can graduate',
                    'completion ready learners'
                ],
                'keywords': ['graduation', 'eligible', 'ready', 'completion', 'graduate'],
                'sql': "SELECT s.First_Name, s.Last_Name, s.Cohort_#, g.Overall_CGPA FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email WHERE g.Courses_Incomplete = 0 AND g.Overall_CGPA >= 3.0 AND s.Status = 'Active' ORDER BY s.Cohort_#, g.Overall_CGPA DESC",
                'parameters': [],
                'description': 'Show students eligible for graduation'
            },
            {
                'id': 8,
                'name': 'cohort_performance_comparison',
                'patterns': [
                    'compare cohort performance',
                    'which cohort is performing best',
                    'cohort academic comparison',
                    'performance by cohort'
                ],
                'keywords': ['cohort', 'performance', 'comparison', 'academic', 'best'],
                'sql': "SELECT s.Cohort_#, COUNT(*) as Total_Students, ROUND(AVG(g.Overall_CGPA), 2) as Avg_CGPA, SUM(CASE WHEN g.Courses_Incomplete = 0 THEN 1 ELSE 0 END) as Completed_All FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email GROUP BY s.Cohort_# ORDER BY Avg_CGPA DESC",
                'parameters': [],
                'description': 'Compare academic performance across cohorts'
            },
            {
                'id': 9,
                'name': 'dissertation_supervision_status',
                'patterns': [
                    'dissertation supervision status',
                    'faculty workload distribution',
                    'supervisor assignments',
                    'who is supervising whom'
                ],
                'keywords': ['dissertation', 'supervision', 'faculty', 'workload', 'supervisor'],
                'sql': "SELECT Chair, COUNT(*) AS Students_Supervised FROM Dissertation WHERE Chair IS NOT NULL AND Chair != '' GROUP BY Chair ORDER BY Students_Supervised DESC",
                'parameters': [],
                'description': 'Show dissertation supervision workload'
            },
            {
                'id': 10,
                'name': 'students_without_supervision',
                'patterns': [
                    'students without dissertation chairs',
                    'unassigned supervision',
                    'students needing supervisors',
                    'supervision assignment gaps'
                ],
                'keywords': ['without', 'supervision', 'unassigned', 'supervisors', 'gaps'],
                'sql': "SELECT First_Name, Last_Name, Email FROM Dissertation WHERE Chair IS NULL OR Chair = ''",
                'parameters': [],
                'description': 'Show students without assigned dissertation chairs'
            },
            {
                'id': 11,
                'name': 'international_vs_domestic',
                'patterns': [
                    'international vs domestic students',
                    'student origin breakdown',
                    'how many international students',
                    'domestic vs international ratio'
                ],
                'keywords': ['international', 'domestic', 'origin', 'breakdown', 'ratio'],
                'sql': "SELECT CASE WHEN Batch LIKE '%International%' THEN 'International' ELSE 'Domestic' END AS Student_Type, COUNT(*) AS Count FROM Student_List GROUP BY CASE WHEN Batch LIKE '%International%' THEN 'International' ELSE 'Domestic' END",
                'parameters': [],
                'description': 'Show international vs domestic student distribution'
            },
            {
                'id': 12,
                'name': 'course_completion_rates',
                'patterns': [
                    'course completion rates',
                    'how many completed all courses',
                    'academic progress overview',
                    'completion statistics'
                ],
                'keywords': ['course', 'completion', 'rates', 'progress', 'statistics'],
                'sql': "SELECT Courses_Completed, COUNT(*) as Student_Count FROM Gradesheet GROUP BY Courses_Completed ORDER BY Courses_Completed DESC",
                'parameters': [],
                'description': 'Show course completion distribution'
            },
            {
                'id': 13,
                'name': 'dissertation_progress_tracking',
                'patterns': [
                    'dissertation progress tracking',
                    'thesis completion status',
                    'research milestone tracking',
                    'dissertation phase overview'
                ],
                'keywords': ['dissertation', 'progress', 'thesis', 'completion', 'milestone'],
                'sql': "SELECT Grading_Status, COUNT(*) as Count FROM Dissertation WHERE Grading_Status IS NOT NULL GROUP BY Grading_Status ORDER BY Count DESC",
                'parameters': [],
                'description': 'Track dissertation progress across all students'
            },
            {
                'id': 14,
                'name': 'students_by_time_slot',
                'patterns': [
                    'students by class time slots',
                    'slot distribution',
                    'class timing preferences',
                    'scheduling overview'
                ],
                'keywords': ['slot', 'time', 'class', 'scheduling', 'distribution'],
                'sql': "SELECT Slot, COUNT(*) AS Student_Count FROM Student_List WHERE Slot IS NOT NULL GROUP BY Slot ORDER BY Student_Count DESC",
                'parameters': [],
                'description': 'Show student distribution by class time slots'
            },
            {
                'id': 15,
                'name': 'contact_information_gaps',
                'patterns': [
                    'students with missing contact info',
                    'incomplete contact details',
                    'communication gaps',
                    'contact information audit'
                ],
                'keywords': ['contact', 'missing', 'incomplete', 'communication', 'gaps'],
                'sql': "SELECT First_Name, Last_Name, Email FROM Student_List WHERE Contact IS NULL OR Contact = ''",
                'parameters': [],
                'description': 'Identify students with missing contact information'
            },
            {
                'id': 16,
                'name': 'students_by_cgpa_range',
                'patterns': [
                    'students with CGPA above {cgpa}',
                    'learners with CGPA below {cgpa}',
                    'students with CGPA between {cgpa1} and {cgpa2}',
                    'high performing students',
                    'identify learners with CGPA less than {cgpa}',
                    'show students with CGPA less than {cgpa}',
                    'find learners with CGPA below {cgpa}',
                    'students with low CGPA below {cgpa}',
                    'learners needing attention CGPA less than {cgpa}'
                ],
                'keywords': ['cgpa', 'above', 'below', 'between', 'high', 'performing', 'less', 'low', 'identify', 'learners', 'needing', 'attention'],
                'sql': "SELECT s.First_Name, s.Last_Name, g.Overall_CGPA, s.Cohort_# FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email WHERE g.Overall_CGPA < {cgpa} ORDER BY g.Overall_CGPA ASC",
                'parameters': ['cgpa'],
                'description': 'Show students by CGPA criteria'
            },
            {
                'id': 17,
                'name': 'top_performers',
                'patterns': [
                    'top {limit} students by CGPA',
                    'best performing students',
                    'highest CGPA students',
                    'top performers list'
                ],
                'keywords': ['top', 'best', 'highest', 'performers', 'cgpa'],
                'sql': "SELECT First_Name, Last_Name, Overall_CGPA FROM Gradesheet ORDER BY Overall_CGPA DESC LIMIT {limit}",
                'parameters': ['limit'],
                'description': 'Show top performing students by CGPA'
            },
            {
                'id': 18,
                'name': 'students_by_country',
                'patterns': [
                    'students from {country}',
                    'learners by country',
                    'how many students from each country',
                    'country wise distribution'
                ],
                'keywords': ['country', 'from', 'distribution', 'students', 'learners'],
                'sql': "SELECT First_Name, Last_Name, Country_Of_Origin FROM Student_List WHERE Country_Of_Origin = '{country}'",
                'parameters': ['country'],
                'description': 'Show students from specific country'
            },
            {
                'id': 19,
                'name': 'dissertation_status_by_name',
                'patterns': [
                    'dissertation status for {name}',
                    'thesis progress of {name}',
                    'research status for {name}',
                    'check dissertation for {name}'
                ],
                'keywords': ['dissertation', 'thesis', 'research', 'status', 'progress'],
                'sql': "SELECT \"Learner Name\", \"Dissertation mode\", \"Grading Status\" FROM Dissertation WHERE \"Learner Name\" LIKE '%{name}%' AND \"Dissertation mode\" IS NOT NULL AND \"Dissertation mode\" != '0'",
                'parameters': ['name'],
                'description': 'Check dissertation status for specific student'
            },
            {
                'id': 20,
                'name': 'incomplete_courses_analysis',
                'patterns': [
                    'students with incomplete courses',
                    'learners with pending courses',
                    'incomplete coursework analysis',
                    'course completion gaps'
                ],
                'keywords': ['incomplete', 'pending', 'courses', 'coursework', 'gaps'],
                'sql': "SELECT First_Name, Last_Name, Courses_Incomplete FROM Gradesheet WHERE Courses_Incomplete > 0 ORDER BY Courses_Incomplete DESC",
                'parameters': [],
                'description': 'Show students with incomplete courses'
            },
            {
                'id': 21,
                'name': 'average_cgpa_by_cohort',
                'patterns': [
                    'average CGPA by cohort',
                    'cohort performance averages',
                    'mean CGPA per cohort',
                    'cohort academic averages'
                ],
                'keywords': ['average', 'mean', 'cgpa', 'cohort', 'performance'],
                'sql': "SELECT s.Cohort_#, ROUND(AVG(g.Overall_CGPA), 2) AS Avg_CGPA FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email GROUP BY s.Cohort_# ORDER BY s.Cohort_#",
                'parameters': [],
                'description': 'Show average CGPA for each cohort'
            },
            {
                'id': 22,
                'name': 'students_by_batch_type',
                'patterns': [
                    'international vs domestic students',
                    'batch type distribution',
                    'student origin analysis',
                    'domestic and international breakdown'
                ],
                'keywords': ['international', 'domestic', 'batch', 'origin', 'breakdown'],
                'sql': "SELECT CASE WHEN Batch LIKE '%International%' THEN 'International' ELSE 'Domestic' END AS Batch_Type, COUNT(*) AS Count FROM Student_List GROUP BY CASE WHEN Batch LIKE '%International%' THEN 'International' ELSE 'Domestic' END",
                'parameters': [],
                'description': 'Show international vs domestic student distribution'
            },
            {
                'id': 23,
                'name': 'irb_submission_status',
                'patterns': [
                    'IRB submission status',
                    'who submitted IRB',
                    'pending IRB submissions',
                    'research ethics approval'
                ],
                'keywords': ['irb', 'submission', 'ethics', 'approval', 'research'],
                'sql': "SELECT CASE WHEN IRB = 'Not Submitted' THEN 'Not Submitted' WHEN IRB IS NOT NULL AND IRB != '' THEN 'Submitted' ELSE 'Pending' END AS IRB_Status, COUNT(*) AS Count FROM Dissertation GROUP BY CASE WHEN IRB = 'Not Submitted' THEN 'Not Submitted' WHEN IRB IS NOT NULL AND IRB != '' THEN 'Submitted' ELSE 'Pending' END",
                'parameters': [],
                'description': 'Show IRB submission statistics'
            },
            {
                'id': 24,
                'name': 'topic_approval_status',
                'patterns': [
                    'topic approval status',
                    'pending topic approvals',
                    'approved research topics',
                    'topic proposal tracking'
                ],
                'keywords': ['topic', 'approval', 'pending', 'approved', 'proposal'],
                'sql': "SELECT CASE WHEN Topic_Proposal_Approval = 'Approved' THEN 'Approved' ELSE 'Pending/Not Approved' END AS Approval_Status, COUNT(*) AS Count FROM Dissertation GROUP BY CASE WHEN Topic_Proposal_Approval = 'Approved' THEN 'Approved' ELSE 'Pending/Not Approved' END",
                'parameters': [],
                'description': 'Show topic approval statistics'
            },
            {
                'id': 25,
                'name': 'students_needing_attention',
                'patterns': [
                    'students needing immediate attention',
                    'critical intervention cases',
                    'high priority students',
                    'urgent academic cases'
                ],
                'keywords': ['attention', 'intervention', 'critical', 'urgent', 'priority'],
                'sql': "SELECT s.First_Name, s.Last_Name, s.Cohort_#, g.Overall_CGPA, g.Courses_Incomplete FROM Student_List s JOIN Gradesheet g ON s.Email = g.Email WHERE g.Overall_CGPA < 2.5 OR g.Courses_Incomplete > 3 ORDER BY g.Overall_CGPA ASC, g.Courses_Incomplete DESC",
                'parameters': [],
                'description': 'Identify students requiring immediate attention'
            },
            {
                'id': 26,
                'name': 'email_domain_analysis',
                'patterns': [
                    'email domain distribution',
                    'student email providers',
                    'email domain statistics',
                    'communication platform analysis'
                ],
                'keywords': ['email', 'domain', 'providers', 'communication', 'platform'],
                'sql': "SELECT SUBSTR(Email, INSTR(Email, '@') + 1) AS Email_Domain, COUNT(*) AS Count FROM Student_List GROUP BY SUBSTR(Email, INSTR(Email, '@') + 1) ORDER BY Count DESC",
                'parameters': [],
                'description': 'Analyze email domain distribution'
            },
            {
                'id': 27,
                'name': 'course_grade_distribution',
                'patterns': [
                    'grade distribution for courses',
                    'course performance analysis',
                    'grade patterns by course',
                    'academic performance breakdown'
                ],
                'keywords': ['grade', 'distribution', 'course', 'performance', 'academic'],
                'sql': "SELECT 'DBA 805' AS Course, DBA_805_Grade AS Grade, COUNT(*) AS Count FROM Gradesheet WHERE DBA_805_Grade IS NOT NULL GROUP BY DBA_805_Grade UNION SELECT 'DBA 806', DBA_806_Grade, COUNT(*) FROM Gradesheet WHERE DBA_806_Grade IS NOT NULL GROUP BY DBA_806_Grade ORDER BY Course, Count DESC",
                'parameters': [],
                'description': 'Show grade distribution across courses'
            },
            {
                'id': 28,
                'name': 'research_methodology_preferences',
                'patterns': [
                    'dissertation mode preferences',
                    'research methodology distribution',
                    'thesis type analysis',
                    'research approach statistics'
                ],
                'keywords': ['methodology', 'dissertation', 'research', 'approach', 'thesis'],
                'sql': "SELECT \"Dissertation mode\", COUNT(*) AS Count FROM Dissertation WHERE \"Dissertation mode\" IS NOT NULL AND \"Dissertation mode\" != '0' GROUP BY \"Dissertation mode\" ORDER BY Count DESC",
                'parameters': [],
                'description': 'Show research methodology preferences'
            },
            {
                'id': 29,
                'name': 'comprehensive_student_overview',
                'patterns': [
                    'complete student overview',
                    'full program statistics',
                    'comprehensive data summary',
                    'overall program metrics'
                ],
                'keywords': ['comprehensive', 'complete', 'overview', 'statistics', 'metrics'],
                'sql': "SELECT 'Total Students' AS Metric, COUNT(*) AS Value FROM Student_List UNION SELECT 'Active Students', COUNT(*) FROM Student_List WHERE Status IN ('Active', 'Active / Deferred In') UNION SELECT 'Total Cohorts', COUNT(DISTINCT Cohort_#) FROM Student_List UNION SELECT 'Avg CGPA', ROUND(AVG(Overall_CGPA), 2) FROM Gradesheet",
                'parameters': [],
                'description': 'Comprehensive program overview'
            },
            {
                'id': 30,
                'name': 'dynamic_search_query',
                'patterns': [
                    'search for {query}',
                    'find information about {query}',
                    'show me data on {query}',
                    'lookup {query}'
                ],
                'keywords': ['search', 'find', 'lookup', 'information', 'data'],
                'sql': "SELECT * FROM Student_List WHERE First_Name LIKE '%{query}%' OR Last_Name LIKE '%{query}%' OR Email LIKE '%{query}%' LIMIT 10",
                'parameters': ['query'],
                'description': 'Dynamic search across student data'
            },
            {
                'id': 31,
                'name': 'webapp_navigation_help',
                'patterns': [
                    'how to navigate the webapp',
                    'webapp navigation guide',
                    'how to use the application',
                    'webapp tutorial',
                    'application help'
                ],
                'keywords': ['navigation', 'webapp', 'tutorial', 'help', 'guide'],
                'sql': "",
                'parameters': [],
                'description': 'Provide webapp navigation guidance'
            },
            {
                'id': 32,
                'name': 'dashboard_help',
                'patterns': [
                    'how to use dashboard',
                    'dashboard features',
                    'dashboard help',
                    'main dashboard guide'
                ],
                'keywords': ['dashboard', 'features', 'main', 'overview'],
                'sql': "",
                'parameters': [],
                'description': 'Guide users on dashboard functionality'
            },
            {
                'id': 33,
                'name': 'learners_page_help',
                'patterns': [
                    'how to view learners',
                    'learners page help',
                    'student list guide',
                    'how to search students'
                ],
                'keywords': ['learners', 'students', 'search', 'view', 'list'],
                'sql': "",
                'parameters': [],
                'description': 'Help with learners page functionality'
            },
            {
                'id': 34,
                'name': 'document_creation_help',
                'patterns': [
                    'how to create documents',
                    'document generation help',
                    'bulk document creation',
                    'document automation guide'
                ],
                'keywords': ['document', 'creation', 'generation', 'bulk', 'automation'],
                'sql': "",
                'parameters': [],
                'description': 'Guide users on document creation features'
            },
            {
                'id': 35,
                'name': 'email_automation_help',
                'patterns': [
                    'how to send emails',
                    'email automation help',
                    'bulk email sending',
                    'email features guide'
                ],
                'keywords': ['email', 'automation', 'sending', 'bulk', 'features'],
                'sql': "",
                'parameters': [],
                'description': 'Help with email automation features'
            },
            {
                'id': 36,
                'name': 'reminder_system_help',
                'patterns': [
                    'how to set reminders',
                    'reminder system help',
                    'session reminders guide',
                    'reminder automation'
                ],
                'keywords': ['reminder', 'system', 'session', 'automation', 'notifications'],
                'sql': "",
                'parameters': [],
                'description': 'Guide users on reminder system'
            },
            {
                'id': 37,
                'name': 'folder_creation_help',
                'patterns': [
                    'how to create folders',
                    'folder organization help',
                    'bulk folder creation',
                    'folder management guide'
                ],
                'keywords': ['folder', 'creation', 'organization', 'management', 'bulk'],
                'sql': "",
                'parameters': [],
                'description': 'Help with folder creation and management'
            },
            {
                'id': 38,
                'name': 'chatbot_help',
                'patterns': [
                    'how to use chatbot',
                    'chatbot features',
                    'chatbot help',
                    'AI assistant guide'
                ],
                'keywords': ['chatbot', 'ai', 'assistant', 'features', 'help'],
                'sql': "",
                'parameters': [],
                'description': 'Guide users on chatbot functionality'
            },
            {
                'id': 39,
                'name': 'admin_panel_help',
                'patterns': [
                    'admin panel help',
                    'user management guide',
                    'admin features',
                    'how to manage users'
                ],
                'keywords': ['admin', 'panel', 'user', 'management', 'features'],
                'sql': "",
                'parameters': [],
                'description': 'Help with admin panel features'
            },
            {
                'id': 40,
                'name': 'login_help',
                'patterns': [
                    'login help',
                    'how to login',
                    'authentication guide',
                    'login issues'
                ],
                'keywords': ['login', 'authentication', 'access', 'password', 'issues'],
                'sql': "",
                'parameters': [],
                'description': 'Help with login and authentication'
            },
            {
                'id': 41,
                'name': 'total_live_sessions',
                'patterns': [
                    'total number of live sessions',
                    'how many live sessions',
                    'give me the total number of live sessions',
                    'total live sessions count',
                    'count of live sessions',
                    'live sessions total'
                ],
                'keywords': ['total', 'live', 'sessions', 'number', 'count', 'how', 'many'],
                'sql': "SELECT COUNT(*) as Total_Live_Sessions FROM [Live Session]",
                'parameters': [],
                'description': 'Get total count of live sessions'
            },
            {
                'id': 42,
                'name': 'live_sessions_by_course',
                'patterns': [
                    'live sessions by course',
                    'sessions per course',
                    'how many sessions per course',
                    'course wise live sessions'
                ],
                'keywords': ['live', 'sessions', 'course', 'per', 'wise'],
                'sql': "SELECT [Program] as Program_Name, COUNT(*) as Session_Count FROM [Live Session] GROUP BY [Program] ORDER BY Session_Count DESC",
                'parameters': [],
                'description': 'Show live sessions count by course'
            }
        ]   
    
    def _initialize_keywords_mapping(self) -> Dict[str, List[str]]:
        """Initialize keyword mappings for better fuzzy matching"""
        return {
            'students': ['learners', 'pupils', 'scholars', 'participants'],
            'active': ['current', 'enrolled', 'ongoing'],
            'cohort': ['batch', 'group', 'class', 'year'],
            'cgpa': ['gpa', 'grades', 'marks', 'score', 'performance'],
            'dissertation': ['thesis', 'research', 'project', 'paper'],
            'email': ['mail', 'address', 'contact'],
            'count': ['number', 'total', 'how many', 'quantity'],
            'show': ['display', 'list', 'get', 'find', 'retrieve'],
            'status': ['state', 'condition', 'progress'],
            'professor': ['supervisor', 'advisor', 'chair', 'mentor', 'faculty']
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        # Convert to lowercase
        text = text.lower().strip()
        
        # Replace synonyms with standard keywords
        for standard_word, synonyms in self.keywords_mapping.items():
            for synonym in synonyms:
                text = re.sub(r'\b' + re.escape(synonym) + r'\b', standard_word, text)
        
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def get_ai_response(self, user_message: str, context: str = "") -> str:
        """Get response from NVIDIA Qwen AI model"""
        # Check if AI is available
        if not self.ai_available or not self.nvidia_client:
            return f"I'm having trouble connecting to the AI service right now. However, I can still help you with specific student queries like:\n\n• Search for students by name or email\n• Get cohort statistics\n• Find students with low grades\n• Check dissertation progress\n\nPlease try asking about specific student data."
        
        try:
            # Prepare system prompt with context about EduOps360
            system_prompt = """You are an AI assistant for EduOps360, an educational management platform for a DBA (Doctor of Business Administration) program. 

You help program coordinators and administrators with:
- Student information and academic performance
- Cohort statistics and analytics
- Course completion tracking
- Dissertation progress monitoring
- General educational operations support

Be helpful, professional, and concise. If you don't have specific data, guide users on how to find the information they need within the platform.

Context about the platform:
- Manages DBA students across multiple cohorts
- Tracks coursework (7 courses) and dissertation phases
- Monitors CGPA, course completion, and academic progress
- Handles both international and domestic students
- Provides automation tools for documents, emails, and reminders

""" + (f"Additional context: {context}" if context else "")

            # Handle different client types
            if hasattr(self.nvidia_client, 'chat'):
                # New OpenAI client style
                completion = self.nvidia_client.chat.completions.create(
                    model="qwen/qwen3-coder-480b-a35b-instruct",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    top_p=0.8,
                    max_tokens=4096,
                    stream=False
                )
                return completion.choices[0].message.content
            else:
                # Legacy OpenAI client style
                completion = self.nvidia_client.ChatCompletion.create(
                    model="qwen/qwen3-coder-480b-a35b-instruct",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    top_p=0.8,
                    max_tokens=4096,
                    stream=False
                )
                return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            
            # Provide a more helpful fallback response
            return f"I'm having trouble connecting to the AI service right now. However, I can still help you with specific student queries like:\n\n• Search for students by name or email\n• Get cohort statistics\n• Find students with low grades\n• Check dissertation progress\n\nPlease try asking about specific student data, or try your question again in a moment."
    
    def extract_parameters_from_query(self, query: str, pattern: str) -> Dict[str, str]:
        """Extract parameters from user query based on pattern"""
        parameters = {}
        
        # Create regex pattern from template
        regex_pattern = pattern
        param_names = re.findall(r'\{(\w+)\}', pattern)
        
        for param in param_names:
            regex_pattern = regex_pattern.replace(f'{{{param}}}', r'(\S+)')
        
        # Try to match the pattern
        match = re.search(regex_pattern, query, re.IGNORECASE)
        if match:
            for i, param in enumerate(param_names):
                parameters[param] = match.group(i + 1)
        else:
            # Fallback: extract common parameter types
            parameters.update(self.extract_learner_info(query))
            
            # Extract numbers for limits, CGPA thresholds, etc.
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', query)
            if numbers:
                if 'limit' in param_names:
                    parameters['limit'] = numbers[0]
                elif 'cgpa' in param_names:
                    parameters['cgpa'] = numbers[0]
        
        return parameters
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using SequenceMatcher"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_best_matching_query(self, user_query: str) -> Tuple[Dict[str, Any], float, Dict[str, str]]:
        """Find the best matching query pattern using fuzzy matching"""
        normalized_query = self.normalize_text(user_query)
        best_match = None
        best_score = 0.0
        best_parameters = {}
        
        for pattern_data in self.query_patterns:
            # Check direct pattern matches first
            for pattern in pattern_data['patterns']:
                normalized_pattern = self.normalize_text(pattern.replace('{', '').replace('}', ''))
                
                # Calculate similarity
                similarity = self.calculate_similarity(normalized_query, normalized_pattern)
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = pattern_data
                    best_parameters = self.extract_parameters_from_query(user_query, pattern)
            
            # Check keyword-based matching
            keyword_matches = 0
            total_keywords = len(pattern_data['keywords'])
            
            for keyword in pattern_data['keywords']:
                if keyword in normalized_query:
                    keyword_matches += 1
            
            keyword_score = keyword_matches / total_keywords if total_keywords > 0 else 0
            
            # Combine similarity and keyword scores
            combined_score = (similarity * 0.7) + (keyword_score * 0.3)
            
            if combined_score > best_score:
                best_score = combined_score
                best_match = pattern_data
                best_parameters = self.extract_parameters_from_query(user_query, pattern_data['patterns'][0])
        
        return best_match, best_score, best_parameters
    
    def execute_smart_query(self, user_query: str) -> str:
        """Execute smart query matching and return results"""
        try:
            # Find best matching pattern
            best_match, confidence, parameters = self.find_best_matching_query(user_query)
            
            if not best_match or confidence < 0.3:  # Minimum confidence threshold
                return self.handle_unmatched_query(user_query)
            
            # Check if this is a webapp guidance query (patterns 31-40)
            if best_match['id'] >= 31 and best_match['id'] <= 40:
                return self.get_webapp_guidance(best_match['name'])
            
            # Validate required parameters for data queries
            missing_params = []
            for param in best_match['parameters']:
                if param not in parameters or not parameters[param]:
                    missing_params.append(param)
            
            if missing_params:
                return f"I found a matching query pattern but I need more information. Please provide: {', '.join(missing_params)}"
            
            # Execute the SQL query for data patterns
            sql_query = best_match['sql']
            
            # Skip SQL execution for webapp guidance patterns
            if not sql_query:
                return self.get_webapp_guidance(best_match['name'])
            
            # Substitute parameters in SQL
            for param, value in parameters.items():
                sql_query = sql_query.replace(f'{{{param}}}', str(value))
            
            # Execute query and format results
            results = self.execute_sql_query(sql_query)
            
            if not results:
                return f"No results found for your query: {best_match['description']}"
            
            return self.format_query_results(results, best_match['name'], best_match['description'])
            
        except Exception as e:
            logger.error(f"Error in smart query execution: {e}")
            return f"Sorry, I encountered an error processing your query: {str(e)}"
    
    def execute_sql_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results"""
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            # Update table names to match your database schema
            sql_query = sql_query.replace('Student_List', '"Student List"')
            sql_query = sql_query.replace('Gradesheet', '"Gradesheet"')
            sql_query = sql_query.replace('Dissertation', '"Dissertation"')
            
            # Handle column name mappings
            column_mappings = {
                'First_Name': '"First Name"',
                'Last_Name': '"Last Name"',
                'Cohort_#': '"Cohort #"',
                'Overall_CGPA': '"Overall CGPA"',
                'Courses_Incomplete': '"Courses Incomplete"',
                'Dissertation_Mode': '"Dissertation mode"',
                'Grading_Status': '"Grading Status"',
                'Topic_Proposal_Approval': '"Topic Proposal Approval"',
                'Dissertation_Document': '"Dissertation Document"',
                'Country_Of_Origin': '"Country Of Origin"',
                'DBA_805_Credit': '"DBA 805 Credit"',
                'DBA_806_Credit': '"DBA 806 Credit"',
                'DBA_863_Credit': '"DBA 863 Credit"',
                'DBA_860_Credit': '"DBA 860 Credit"',
                'DBA_861_Credit': '"DBA 861 Credit"',
                'DBA_862_Credit': '"DBA 862 Credit"',
                'DBA_864_Credit': '"DBA 864 Credit"'
            }
            
            for old_col, new_col in column_mappings.items():
                sql_query = sql_query.replace(old_col, new_col)
            
            logger.info(f"Executing SQL: {sql_query}")
            df = pd.read_sql_query(sql_query, conn)
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            return []
        finally:
            conn.close()
    
    def format_query_results(self, results: List[Dict[str, Any]], query_name: str, description: str) -> str:
        """Format query results for display"""
        if not results:
            return f"No results found for: {description}"
        
        response = f"**📊 {description}**\n\n"
        
        # Handle different result types
        if query_name == 'total_unique_learners':
            total = results[0].get('Total_Unique_Learners', 0)
            response += f"**Total Unique Learners:** {total}\n"
        
        elif query_name == 'count_active_learners_per_cohort':
            response += "**Active Learners by Cohort:**\n"
            for row in results:
                cohort = row.get('Cohort #', 'N/A')
                count = row.get('Active_Learners', 0)
                response += f"- **Cohort {cohort}:** {count} active learners\n"
        
        elif query_name == 'average_cgpa_per_cohort':
            response += "**Average CGPA by Cohort:**\n"
            for row in results:
                cohort = row.get('Cohort #', 'N/A')
                avg_cgpa = row.get('Avg_CGPA', 0)
                response += f"- **Cohort {cohort}:** {avg_cgpa:.2f}\n"
        
        elif query_name == 'learners_by_dissertation_mode':
            response += "**Students by Dissertation Mode:**\n"
            for row in results:
                mode = row.get('Dissertation mode', 'N/A')
                count = row.get('Count', 0)
                response += f"- **{mode}:** {count} students\n"
        
        else:
            # Generic table format
            if len(results) == 1:
                # Single result
                for key, value in results[0].items():
                    if value is not None:
                        response += f"- **{key}:** {value}\n"
            else:
                # Multiple results - show first 10
                for i, row in enumerate(results[:10], 1):
                    response += f"**{i}. "
                    
                    # Show name if available
                    if 'First Name' in row and 'Last Name' in row:
                        response += f"{row['First Name']} {row['Last Name']}"
                    elif 'First_Name' in row and 'Last_Name' in row:
                        response += f"{row['First_Name']} {row['Last_Name']}"
                    else:
                        response += "Record"
                    
                    response += "**\n"
                    
                    # Show key fields
                    for key, value in row.items():
                        if value is not None and key not in ['First Name', 'Last Name', 'First_Name', 'Last_Name']:
                            response += f"   - {key}: {value}\n"
                    response += "\n"
                
                if len(results) > 10:
                    response += f"*... and {len(results) - 10} more results*\n"
        
        return response
    
    def handle_unmatched_query(self, user_query: str) -> str:
        """Handle queries that don't match any pattern using intelligent fallback"""
        # First try intelligent query handler
        try:
            intelligent_response = self.intelligent_query_handler(user_query)
            if intelligent_response and not intelligent_response.startswith("I couldn't find an exact match"):
                return intelligent_response
        except Exception as e:
            logger.error(f"Intelligent handler failed: {e}")
        
        # Fallback to suggestion system
        return self.suggest_similar_queries(user_query)
    

    def generate_dynamic_sql(self, user_query: str) -> str:
        """Generate SQL queries dynamically based on user intent"""
        query_lower = user_query.lower()
        
        # Table and column mappings
        tables = {
            'student': '"Student List"',
            'grade': '"Gradesheet"', 
            'dissertation': '"Dissertation"'
        }
        
        columns = {
            'name': 'First_Name, Last_Name',
            'email': 'Email',
            'cohort': 'Cohort_#',
            'status': 'Status',
            'cgpa': 'Overall_CGPA',
            'courses': 'Courses_Completed, Courses_Incomplete',
            'chair': 'Chair',
            'mode': 'Dissertation_Mode'
        }
        
        # Detect intent and generate appropriate SQL
        if any(word in query_lower for word in ['count', 'how many', 'total']):
            if 'student' in query_lower or 'learner' in query_lower:
                return "SELECT COUNT(*) as Total_Count FROM \"Student List\""
            elif 'cohort' in query_lower:
                return "SELECT COUNT(DISTINCT Cohort_#) as Total_Cohorts FROM \"Student List\""
        
        elif any(word in query_lower for word in ['average', 'mean', 'avg']):
            if 'cgpa' in query_lower:
                return "SELECT ROUND(AVG(Overall_CGPA), 2) as Average_CGPA FROM \"Gradesheet\""
        
        elif any(word in query_lower for word in ['highest', 'maximum', 'max']):
            if 'cgpa' in query_lower:
                return "SELECT First_Name, Last_Name, Overall_CGPA FROM \"Gradesheet\" ORDER BY Overall_CGPA DESC LIMIT 1"
        
        elif any(word in query_lower for word in ['lowest', 'minimum', 'min']):
            if 'cgpa' in query_lower:
                return "SELECT First_Name, Last_Name, Overall_CGPA FROM \"Gradesheet\" ORDER BY Overall_CGPA ASC LIMIT 1"
        
        # Default fallback
        return "SELECT First_Name, Last_Name, Email FROM \"Student List\" LIMIT 5"
    
    def intelligent_query_handler(self, user_query: str) -> str:
        """Handle queries not covered by predefined patterns"""
        try:
            # Try to generate dynamic SQL
            sql_query = self.generate_dynamic_sql(user_query)
            results = self.execute_sql_query(sql_query)
            
            if results:
                return self.format_dynamic_results(results, user_query)
            else:
                return self.suggest_similar_queries(user_query)
                
        except Exception as e:
            logger.error(f"Error in intelligent query handler: {e}")
            return self.suggest_similar_queries(user_query)
    
    def format_dynamic_results(self, results: List[Dict[str, Any]], original_query: str) -> str:
        """Format results from dynamic queries"""
        if not results:
            return "No results found for your query."
        
        response = f"**📊 Results for: {original_query}**\n\n"
        
        if len(results) == 1 and len(results[0]) == 1:
            # Single metric result
            key, value = list(results[0].items())[0]
            response += f"**{key.replace('_', ' ').title()}:** {value}\n"
        else:
            # Multiple results
            for i, row in enumerate(results[:10], 1):
                response += f"**{i}. "
                if 'First_Name' in row and 'Last_Name' in row:
                    response += f"{row['First_Name']} {row['Last_Name']}**\n"
                else:
                    response += "Record**\n"
                
                for key, value in row.items():
                    if key not in ['First_Name', 'Last_Name'] and value is not None:
                        response += f"   - {key.replace('_', ' ').title()}: {value}\n"
                response += "\n"
        
        return response
    
    def suggest_similar_queries(self, user_query: str) -> str:
        """Suggest similar queries when no match is found"""
        suggestions = [
            "Total unique learners",
            "Active students by cohort",
            "Students at academic risk", 
            "Graduation eligible students",
            "Faculty supervision workload",
            "Average CGPA by cohort",
            "International vs domestic students",
            "Course completion rates",
            "Dissertation progress tracking"
        ]
        
        response = f"I couldn't find an exact match for '{user_query}'. Here are some queries I can help with:\n\n"
        for i, suggestion in enumerate(suggestions[:5], 1):
            response += f"{i}. {suggestion}\n"
        
        response += "\n💡 **Try asking:**\n"
        response += "- 'How many students are active?'\n"
        response += "- 'Show me top 10 students by CGPA'\n"
        response += "- 'Students from cohort C1'\n"
        response += "- 'Average CGPA for each cohort'\n"
        
        return response


    def get_webapp_guidance(self, pattern_name: str) -> str:
        """Provide detailed guidance for webapp functionalities"""
        
        guidance_responses = {
            'webapp_navigation_help': """
🌐 **EduOps360 Webapp Navigation Guide**

**📊 Main Sections:**
• **Dashboard** - Overview of student statistics and key metrics
• **Learners** - Comprehensive student database with search and filters
• **Automation Tools** - Document creation, emails, reminders, folders
• **Chatbot** - AI assistant for queries and guidance
• **Admin Panel** - User management (admin only)

**🧭 Navigation Tips:**
• Use the top navigation bar to switch between sections
• Dashboard provides quick access to all features
• Each section has breadcrumb navigation
• Use the search functionality in Learners section
• Access automation tools from the main dashboard

**💡 Quick Actions:**
• Click on student names to view detailed profiles
• Use filters to narrow down student lists
• Automation tools are accessible from dashboard cards
""",

            'dashboard_help': """
📊 **Dashboard Features Guide**

**🎯 Key Metrics Cards:**
• **Total Students** - Complete enrollment count
• **Active Students** - Currently enrolled learners
• **Cohorts** - Number of active cohorts
• **Average CGPA** - Overall academic performance

**📈 Interactive Charts:**
• **Cohort Distribution** - Visual breakdown by cohort
• **Status Overview** - Active vs inactive students
• **Performance Metrics** - CGPA distributions
• **Geographic Distribution** - International vs domestic

**🚀 Quick Actions:**
• **View All Learners** - Access complete student database
• **Automation Tools** - Document, email, reminder automation
• **Generate Reports** - Export data and analytics
• **Admin Panel** - User management (if admin)

**💡 Pro Tips:**
• Use cohort filters to focus on specific groups
• Click on chart segments for detailed breakdowns
• Dashboard auto-refreshes with latest data
""",

            'learners_page_help': """
👥 **Learners Page Functionality**

**🔍 Search & Filter Options:**
• **Name Search** - Find students by first/last name
• **Email Search** - Locate by email address
• **Cohort Filter** - Filter by specific cohorts
• **Status Filter** - Active, inactive, deferred students
• **Country Filter** - Filter by country of origin

**📋 Student Information Display:**
• **Basic Info** - Name, email, cohort, status
• **Academic Data** - CGPA, courses completed
• **Contact Details** - Phone, address information
• **Batch Information** - International/domestic classification

**🎯 Actions Available:**
• **View Profile** - Click student name for detailed view
• **Export Data** - Download filtered results
• **Bulk Operations** - Select multiple students
• **Quick Stats** - Hover for additional information

**💡 Usage Tips:**
• Use multiple filters for precise results
• Sort columns by clicking headers
• Pagination controls at bottom
• Clear filters to reset view
""",

            'document_creation_help': """
📄 **Document Creation & Automation**

**🚀 Getting Started:**
1. **Upload Template** - Upload your Word document template
2. **Upload Data** - Provide CSV file with student data
3. **Map Fields** - Match CSV columns to template placeholders
4. **Generate** - Create personalized documents

**📝 Template Requirements:**
• Use `{{field_name}}` format for placeholders
• Supported formats: DOCX templates
• Common fields: name, email, cohort, grades
• Test template with sample data first

**📊 Data File Format:**
• CSV format with headers
• Match column names to template fields
• Ensure data quality (no empty critical fields)
• Support for special characters and formatting

**⚡ Bulk Operations:**
• Generate hundreds of documents simultaneously
• Automatic file naming based on student data
• ZIP download for multiple files
• Progress tracking during generation

**📧 Email Integration:**
• Send generated documents via email
• Customize email templates
• Bulk email sending with rate limiting
• Delivery status tracking

**💡 Best Practices:**
• Test with small batches first
• Keep templates simple and clean
• Verify data accuracy before bulk generation
• Use meaningful file naming conventions
""",

            'email_automation_help': """
📧 **Email Automation System**

**✉️ Email Features:**
• **Bulk Email Sending** - Send to multiple recipients
• **Template Support** - Reusable email templates
• **Attachment Handling** - Include documents, files
• **Personalization** - Dynamic content based on data

**🔧 Setup Process:**
1. **Configure SMTP** - Set up email server settings
2. **Create Template** - Design email with placeholders
3. **Upload Recipients** - CSV file with email addresses
4. **Customize Content** - Personalize subject and body
5. **Send & Track** - Monitor delivery status

**📋 Supported Formats:**
• **HTML Emails** - Rich formatting and styling
• **Plain Text** - Simple text-based emails
• **Mixed Content** - Combine text and HTML
• **Attachments** - PDF, DOCX, images

**⚙️ Advanced Features:**
• **Rate Limiting** - Prevent server overload
• **Retry Logic** - Automatic retry for failed sends
• **Delivery Reports** - Track success/failure rates
• **Bounce Handling** - Manage invalid addresses

**💡 Email Best Practices:**
• Use clear, descriptive subject lines
• Test emails before bulk sending
• Respect rate limits to avoid blocking
• Keep attachments under 10MB
• Verify recipient email addresses
""",

            'reminder_system_help': """
🔔 **Session Reminder System**

**📅 Reminder Features:**
• **Session Notifications** - Automated session reminders
• **Professor Alerts** - Notify faculty of upcoming sessions
• **Student Reminders** - Alert learners about sessions
• **Customizable Timing** - Set reminder schedules

**🚀 Setup Process:**
1. **Upload Schedule** - Excel file with session details
2. **Configure Timing** - Set when reminders are sent
3. **Customize Messages** - Personalize reminder content
4. **Set Recipients** - Choose who receives reminders
5. **Activate System** - Enable automatic sending

**📊 Required Data:**
• **Session Details** - Date, time, subject
• **Professor Information** - Name, email, contact
• **Student Lists** - Enrolled learners per session
• **Room/Location** - Physical or virtual meeting details

**⏰ Timing Options:**
• **24 Hours Before** - Day-ahead notifications
• **2 Hours Before** - Last-minute reminders
• **Custom Intervals** - Set your own timing
• **Recurring Reminders** - For regular sessions

**💡 Reminder Tips:**
• Include all essential session information
• Test reminder system with small groups
• Verify contact information accuracy
• Use clear, professional language
• Set appropriate reminder frequency
""",

            'folder_creation_help': """
📁 **Folder Organization & Management**

**🗂️ Bulk Folder Creation:**
• **Student Folders** - Individual folders per learner
• **Cohort Organization** - Structured by cohort/batch
• **Custom Naming** - Flexible naming conventions
• **Nested Structure** - Multi-level folder hierarchies

**🚀 Creation Process:**
1. **Select Template** - Choose folder structure template
2. **Upload Data** - CSV with student/organization data
3. **Configure Structure** - Set folder hierarchy
4. **Customize Names** - Define naming patterns
5. **Generate Folders** - Create entire structure

**📋 Naming Conventions:**
• **Student Format** - LastName_FirstName_Cohort
• **Date Integration** - Include enrollment dates
• **ID Numbers** - Use student ID in folder names
• **Custom Patterns** - Create your own format

**🎯 Use Cases:**
• **Document Organization** - Store student documents
• **Assignment Submission** - Individual submission folders
• **Cohort Management** - Organize by academic groups
• **Archive Structure** - Historical record keeping

**💡 Organization Tips:**
• Plan folder structure before creation
• Use consistent naming conventions
• Consider future scalability
• Test with small batches first
• Maintain backup of folder structures
""",

            'chatbot_help': """
🤖 **AI Chatbot Assistant Guide**

**💬 What I Can Help With:**
• **Student Queries** - Find learner information
• **Academic Data** - CGPA, grades, completion status
• **Statistics** - Enrollment numbers, performance metrics
• **Webapp Guidance** - How to use application features
• **Data Analysis** - Generate insights from your database

**🎯 Query Examples:**
• "Show me active students from cohort C1"
• "Students with CGPA above 3.5"
• "How to create bulk documents?"
• "Average CGPA by cohort"
• "Students needing academic support"

**🔍 Search Capabilities:**
• **Natural Language** - Ask questions naturally
• **Fuzzy Matching** - Handles typos and variations
• **Dynamic Queries** - Adapts to your specific needs
• **Context Awareness** - Understands intent

**📊 Data Insights:**
• **Performance Analytics** - Academic trends and patterns
• **Risk Assessment** - Identify at-risk students
• **Graduation Tracking** - Monitor completion progress
• **Faculty Workload** - Supervision distribution

**💡 Chatbot Tips:**
• Be specific in your queries for better results
• Use student names, emails, or cohorts for searches
• Ask for help if you're unsure about functionality
• I can guide you through any webapp feature
• Try different phrasings if you don't get expected results
""",

            'admin_panel_help': """
👑 **Admin Panel Management**

**🔐 Admin Features:**
• **User Management** - Add, edit, delete users
• **Role Assignment** - Set admin/regular user roles
• **Access Control** - Manage user permissions
• **System Monitoring** - Track user activity

**👥 User Management:**
• **Add Users** - Create new user accounts
• **Edit Profiles** - Update user information
• **Toggle Status** - Activate/deactivate accounts
• **Delete Users** - Remove user accounts
• **Password Reset** - Help users with login issues

**🛡️ Security Features:**
• **Role-Based Access** - Different permission levels
• **Secure Authentication** - Encrypted password storage
• **Session Management** - Automatic logout for security
• **Activity Logging** - Track user actions

**⚙️ Admin Functions:**
• **System Configuration** - Adjust application settings
• **Database Management** - Monitor data integrity
• **Backup Operations** - Ensure data safety
• **Performance Monitoring** - Track system health

**💡 Admin Best Practices:**
• Regularly review user access levels
• Monitor system performance and usage
• Maintain secure password policies
• Keep user information up to date
• Regular backup of critical data
""",

            'login_help': """
🔐 **Login & Authentication Help**

**🚪 Login Process:**
1. **Enter Email** - Use your registered email address
2. **Enter Password** - Type your secure password
3. **Click Login** - Access the application
4. **Stay Logged In** - Session remains active for 24 hours

**🔒 Security Features:**
• **Encrypted Passwords** - Secure password storage
• **Session Timeout** - Automatic logout after inactivity
• **Secure Cookies** - Protected session management
• **Access Control** - Role-based permissions

**❗ Common Issues & Solutions:**

**🔑 Forgot Password:**
• Contact your administrator for password reset
• Ensure you're using the correct email address
• Check for typos in email/password

**🚫 Login Failed:**
• Verify email address is correct
• Check if account is active
• Ensure password is entered correctly
• Contact admin if account is locked

**🌐 Browser Issues:**
• Clear browser cache and cookies
• Try different browser or incognito mode
• Ensure JavaScript is enabled
• Check internet connection

**💡 Login Tips:**
• Use a secure, unique password
• Don't share login credentials
• Log out when finished for security
• Contact admin for any access issues
• Keep your browser updated for best experience
"""
        }
        
        return guidance_responses.get(pattern_name, "I don't have specific guidance for that feature yet. Please contact support for assistance.")

    def extract_learner_info(self, text: str) -> Dict[str, Any]:
        """
        Enhanced learner information extraction from user query
        Returns: {'name': '', 'email': '', 'cohort': '', 'user_id': '', 'first_name': '', 'last_name': ''}
        """
        info = {'name': '', 'email': '', 'cohort': '', 'user_id': '', 'first_name': '', 'last_name': ''}
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            info['email'] = emails[0]
        
        # Extract cohort (C1, C2, etc.)
        cohort_pattern = r'\bC\d+\b'
        cohorts = re.findall(cohort_pattern, text.upper())
        if cohorts:
            info['cohort'] = cohorts[0]
        
        # Extract user ID (numeric)
        user_id_pattern = r'\b\d{4,7}\b'
        user_ids = re.findall(user_id_pattern, text)
        if user_ids:
            info['user_id'] = user_ids[0]
        
        # Enhanced name extraction
        # Remove common query words first
        query_words = ['tell', 'me', 'about', 'show', 'find', 'search', 'for', 'get', 'details', 'information', 'info']
        text_clean = text.lower()
        for word in query_words:
            text_clean = text_clean.replace(word, ' ')
        
        # Look for full name pattern (First Last) in cleaned text
        full_name_pattern = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
        full_names = re.findall(full_name_pattern, text)
        if full_names:
            first_name, last_name = full_names[0]
            info['name'] = f"{first_name} {last_name}"
            info['first_name'] = first_name
            info['last_name'] = last_name
        else:
            # Look for individual first or last name
            words = text.split()
            capitalized_words = [word for word in words if word.istitle() and len(word) > 1 and word.lower() not in query_words]
            
            # If we have capitalized words that aren't email, cohort, etc., treat as names
            name_words = [word for word in capitalized_words 
                         if not re.match(email_pattern, word) 
                         and not re.match(cohort_pattern, word.upper())
                         and not re.match(user_id_pattern, word)]
            
            if len(name_words) == 1:
                # Single name - could be first or last name
                info['name'] = name_words[0]
                info['first_name'] = name_words[0]  # Assume it's first name
            elif len(name_words) > 1:
                # Multiple names - use the first one as first name
                info['first_name'] = name_words[0]
                info['name'] = name_words[0]  # Use first name for search
        
        return info

    def search_learners(self, search_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Enhanced search for learners based on criteria with better name matching
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            query = """
            SELECT DISTINCT 
                sl."First Name", 
                sl."Last Name", 
                sl."Email",
                sl."User ID",
                sl."Cohort #",
                sl."Status",
                sl."Slot",
                sl."Batch",
                g."Overall CGPA",
                g."Courses Completed",
                g."Courses Incomplete"
            FROM "Student List" sl
            LEFT JOIN Gradesheet g ON sl."Email" = g."Email" AND sl."Cohort #" = g."Cohort #"
            WHERE 1=1
            """
            params = []
            
            # Email search (exact match preferred)
            if search_criteria.get('email'):
                query += " AND sl.\"Email\" = ?"
                params.append(search_criteria['email'])
            
            # User ID search
            elif search_criteria.get('user_id'):
                query += " AND sl.\"User ID\" = ?"
                params.append(search_criteria['user_id'])
            
            # Cohort search
            elif search_criteria.get('cohort'):
                query += " AND sl.\"Cohort #\" = ?"
                params.append(search_criteria['cohort'])
            
            # Name-based searches
            elif search_criteria.get('name') or search_criteria.get('first_name') or search_criteria.get('last_name'):
                name_conditions = []
                
                # Full name search (First Name + Last Name)
                if search_criteria.get('name') and ' ' in search_criteria['name']:
                    name_parts = search_criteria['name'].split(' ', 1)
                    if len(name_parts) == 2:
                        name_conditions.append("(sl.\"First Name\" = ? AND sl.\"Last Name\" = ?)")
                        params.extend([name_parts[0], name_parts[1]])
                
                # First name only
                elif search_criteria.get('first_name'):
                    name_conditions.append("sl.\"First Name\" LIKE ?")
                    params.append(f"%{search_criteria['first_name']}%")
                
                # Last name only  
                elif search_criteria.get('last_name'):
                    name_conditions.append("sl.\"Last Name\" LIKE ?")
                    params.append(f"%{search_criteria['last_name']}%")
                
                # Single name (could be first or last name)
                elif search_criteria.get('name'):
                    name_conditions.append("(sl.\"First Name\" LIKE ? OR sl.\"Last Name\" LIKE ?)")
                    params.extend([f"%{search_criteria['name']}%", f"%{search_criteria['name']}%"])
                
                if name_conditions:
                    query += " AND (" + " OR ".join(name_conditions) + ")"
            
            # If no specific criteria but we have a search term, do broad search
            elif search_criteria.get('name'):
                query += """ AND (
                    sl.\"First Name\" LIKE ? OR 
                    sl.\"Last Name\" LIKE ? OR 
                    sl.\"Email\" LIKE ? OR
                    sl.\"User ID\" LIKE ?
                )"""
                params.extend([
                    f"%{search_criteria['name']}%", 
                    f"%{search_criteria['name']}%",
                    f"%{search_criteria['name']}%",
                    f"%{search_criteria['name']}%"
                ])
            
            query += " ORDER BY sl.\"Cohort #\", sl.\"Last Name\", sl.\"First Name\""
            
            logger.info(f"Executing query: {query} with params: {params}")
            df = pd.read_sql_query(query, conn, params=params)
            
            # If no results with exact match, try fuzzy matching for names
            if df.empty and (search_criteria.get('name') or search_criteria.get('first_name') or search_criteria.get('last_name')):
                logger.info("No exact matches found, trying broader search...")
                broader_query = """
                SELECT DISTINCT 
                    sl."First Name", 
                    sl."Last Name", 
                    sl."Email",
                    sl."User ID",
                    sl."Cohort #",
                    sl."Status",
                    sl."Slot",
                    sl."Batch",
                    g."Overall CGPA",
                    g."Courses Completed",
                    g."Courses Incomplete"
                FROM "Student List" sl
                LEFT JOIN Gradesheet g ON sl."Email" = g."Email" AND sl."Cohort #" = g."Cohort #"
                WHERE 1=1
                """
                broader_params = []
                
                if search_criteria.get('name'):
                    broader_query += " AND (sl.\"First Name\" LIKE ? OR sl.\"Last Name\" LIKE ? OR sl.\"Email\" LIKE ?)"
                    broader_params.extend([
                        f"%{search_criteria['name']}%", 
                        f"%{search_criteria['name']}%",
                        f"%{search_criteria['name']}%"
                    ])
                
                broader_query += " ORDER BY sl.\"Cohort #\", sl.\"Last Name\", sl.\"First Name\""
                
                df = pd.read_sql_query(broader_query, conn, params=broader_params)
            
            logger.info(f"Found {len(df)} learners matching criteria")
            return df.to_dict('records')
                
        except Exception as e:
            logger.error(f"Error searching learners: {e}")
            return []
        finally:
            conn.close()
    
    def get_learner_details(self, email: str, cohort: str = None) -> Dict[str, Any]:
        """
        Get comprehensive details for a specific learner
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            # Base learner info
            learner_query = """
            SELECT * FROM "Student List" 
            WHERE "Email" = ?
            """
            params = [email]
            
            if cohort:
                learner_query += " AND \"Cohort #\" = ?"
                params.append(cohort)
            
            learner_df = pd.read_sql_query(learner_query, conn, params=params)
            if learner_df.empty:
                return {}
            
            learner_info = learner_df.iloc[0].to_dict()
            
            # Academic info
            academic_query = """
            SELECT * FROM Gradesheet 
            WHERE "Email" = ? AND "Cohort #" = ?
            """
            academic_df = pd.read_sql_query(academic_query, conn, params=[email, learner_info['Cohort #']])
            academic_info = academic_df.iloc[0].to_dict() if not academic_df.empty else {}
            
            # Dissertation info
            dissertation_query = """
            SELECT * FROM Dissertation 
            WHERE "Email" = ? AND "Cohort #" = ?
            """
            dissertation_df = pd.read_sql_query(dissertation_query, conn, params=[email, learner_info['Cohort #']])
            dissertation_info = dissertation_df.iloc[0].to_dict() if not dissertation_df.empty else {}
            
            # Course grades
            courses = []
            course_columns = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                            'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
            
            for course_col in course_columns:
                if course_col in academic_info and pd.notna(academic_info.get(course_col)):
                    course_name = course_col.replace(' Grade', '')
                    credit_col = course_col.replace('Grade', 'Credit')
                    credit = academic_info.get(credit_col, 'N/A')
                    
                    courses.append({
                        'name': course_name,
                        'grade': academic_info[course_col],
                        'credit': credit
                    })
            
            return {
                'personal_info': learner_info,
                'academic_info': academic_info,
                'dissertation_info': dissertation_info,
                'courses': courses
            }
            
        except Exception as e:
            logger.error(f"Error getting learner details: {e}")
            return {}
        finally:
            conn.close()
    
    def get_cohort_statistics(self, cohort: str = None) -> Dict[str, Any]:
        """
        Get statistics for a cohort or all cohorts
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            # Base query
            query = """
            SELECT 
                sl."Cohort #",
                COUNT(DISTINCT sl."Email") as total_learners,
                SUM(CASE WHEN sl."Status" IN ('Active', 'Active / Deferred In', 'Active (Prospective Deferral)') THEN 1 ELSE 0 END) as active_learners,
                AVG(g."Overall CGPA") as avg_cgpa,
                SUM(CASE WHEN g."Courses Completed" = 7 THEN 1 ELSE 0 END) as completed_all_courses,
                COUNT(DISTINCT CASE WHEN sl."Batch" LIKE '%International%' THEN sl."Email" END) as international_learners,
                COUNT(DISTINCT CASE WHEN sl."Batch" NOT LIKE '%International%' THEN sl."Email" END) as domestic_learners
            FROM "Student List" sl
            LEFT JOIN Gradesheet g ON sl."Email" = g."Email" AND sl."Cohort #" = g."Cohort #"
            WHERE 1=1
            """
            params = []
            
            if cohort:
                query += " AND sl.\"Cohort #\" = ?"
                params.append(cohort)
            
            query += " GROUP BY sl.\"Cohort #\" ORDER BY sl.\"Cohort #\""
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if df.empty:
                return {}
            
            return df.iloc[0].to_dict() if cohort else df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error getting cohort statistics: {e}")
            return {}
        finally:
            conn.close()
    
    def get_low_performing_learners(self, cohort: str = None) -> List[Dict[str, Any]]:
        """
        Get learners with low grades (C+ and below)
        """
        LOW_GRADES = ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I']
        COURSE_COLUMNS = ['DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade', 
                         'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade']
        
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            query = """
            SELECT 
                sl."First Name",
                sl."Last Name", 
                sl."Email",
                sl."Cohort #",
                sl."Status",
                g.*
            FROM "Student List" sl
            JOIN Gradesheet g ON sl."Email" = g."Email" AND sl."Cohort #" = g."Cohort #"
            WHERE sl."Status" IN ('Active', 'Active / Deferred In', 'Active (Prospective Deferral)')
            """
            params = []
            
            if cohort:
                query += " AND sl.\"Cohort #\" = ?"
                params.append(cohort)
            
            df = pd.read_sql_query(query, conn, params=params)
            
            learners_with_low_grades = []
            
            for _, row in df.iterrows():
                low_grade_courses = []
                
                for course in COURSE_COLUMNS:
                    if row[course] in LOW_GRADES:
                        course_name = course.replace(' Grade', '')
                        low_grade_courses.append(f"{course_name}: {row[course]}")
                
                if low_grade_courses:
                    learners_with_low_grades.append({
                        'name': f"{row['First Name']} {row['Last Name']}",
                        'email': row['Email'],
                        'cohort': row['Cohort #'],
                        'low_grade_courses': low_grade_courses,
                        'cgpa': row.get('Overall CGPA', 'N/A')
                    })
            
            return learners_with_low_grades
            
        except Exception as e:
            logger.error(f"Error getting low performing learners: {e}")
            return []
        finally:
            conn.close()
    
# In the chatbot.py file, update the process_query method:

    def process_query(self, user_message: str, session_context: Dict[str, Any] = None) -> str:
        """
        Process user query and return appropriate response with enhanced search
        """
        user_message_lower = user_message.lower().strip()
        user_message_clean = user_message.strip()
        learner_info = self.extract_learner_info(user_message)
        
        # Check if this is a selection from previous multiple results
        if session_context and session_context.get('multiple_results'):
            # Check for numeric selection
            if user_message_clean.isdigit():
                selection = int(user_message_clean)
                multiple_results = session_context['multiple_results']
                
                if 1 <= selection <= len(multiple_results):
                    selected_learner = multiple_results[selection - 1]
                    details = self.get_learner_details(selected_learner['Email'], selected_learner['Cohort #'])
                    
                    if not details:
                        # Clear context even if details fail
                        session_context.pop('multiple_results', None)
                        return f"Found learner but couldn't retrieve detailed information for {selected_learner['First Name']} {selected_learner['Last Name']}."
                    
                    # Clear the multiple results from context AFTER successful selection
                    session_context.pop('multiple_results', None)
                    
                    return self.format_learner_details(selected_learner, details)
                else:
                    return f"Please select a number between 1 and {len(multiple_results)}."
            else:
                # If user types something else instead of a number, clear the context and start over
                session_context.pop('multiple_results', None)
                    
        # ===== BASIC GREETINGS AND CONVERSATIONAL RESPONSES =====
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
        farewells = ['bye', 'goodbye', 'see you', 'see ya', 'take care']
        thanks = ['thanks', 'thank you', 'thank you very much', 'appreciate it']
        how_are = ['how are you', 'how are you doing', 'how do you do', "what's up", 'how is it going']
        
        # Greeting responses
        if any(user_message_lower.startswith(greet) for greet in greetings):
            user_name = session_context.get('user_name', '') if session_context else ''
            if user_name:
                return f"👋 Hello {user_name}! I'm your EduOps assistant. I can help you find learner information, check cohort statistics, identify students with low grades, and more. How can I assist you today?"
            else:
                return "👋 Hello! I'm your EduOps assistant. I can help you find learner information, check cohort statistics, identify students with low grades, and more. How can I assist you today?"
        
        # Farewell responses
        if any(user_message_lower.startswith(farewell) for farewell in farewells):
            return "👋 Goodbye! Feel free to reach out if you need any more information about learners or program statistics. Have a great day!"
        
        # Thank you responses
        if any(user_message_lower.startswith(thank) for thank in thanks):
            return "😊 You're welcome! Is there anything else I can help you with regarding learner information or program data?"
        
        # How are you responses
        if any(user_message_lower == phrase for phrase in how_are):
            return "🤖 I'm functioning well, thank you for asking! Ready to help you with learner data and educational operations. What can I assist you with today?"
        
        # Who are you / what can you do
        if any(phrase in user_message_lower for phrase in ['who are you', 'what are you', 'introduce yourself']):
            return """🤖 **I'm your EduOps Assistant!** 

    I'm here to help you with:
    • **Learner Information** - Search by name, email, user ID
    • **Academic Performance** - Check grades, CGPA, course completion
    • **Cohort Analytics** - Statistics and performance metrics
    • **Low Grade Alerts** - Identify learners needing support
    • **Program Insights** - Overall program health and progress

    Just ask me anything about the learners or type 'help' for detailed options!"""
        
        # Small talk / casual conversation
        casual_responses = {
            'how is the weather': "🌤️ I'm focused on educational data, but I hope the weather is pleasant for you! How can I assist with learner information?",
            'tell me a joke': "😄 Why did the student bring a ladder to class? To reach the high grades! Now, how can I help with real academic data?",
            'what time is it': "⏰ I don't have real-time clock access, but I can tell you about learner progress timelines! What information do you need?",
            'you are smart': "😊 Thank you! I'm designed to help you make data-informed decisions about learner progress. How can I assist you today?",
            'i love you': "💙 I'm here to support your educational operations! Let me know how I can help with learner data and analytics.",
        }
        
        for phrase, response in casual_responses.items():
            if phrase in user_message_lower:
                return response
        
        
        # ===== SMART QUERY PROCESSING FIRST =====
        # Try smart query matching for patterns like CGPA queries, live sessions, etc.
        try:
            smart_response = self.execute_smart_query(user_message)
            # If we get a valid response that's not an unmatched query message, return it
            if smart_response and not smart_response.startswith("I couldn't find an exact match") and not smart_response.startswith("I didn't understand"):
                return smart_response
        except Exception as e:
            logger.error(f"Smart query processing error: {e}")
        
        # ===== SPECIFIC LEARNER SEARCH (Only for specific name/email searches) =====
        # Enhanced search for specific learner - but only if it's clearly a name/email search
        # Exclude queries that contain analytical keywords like 'cgpa', 'total', 'sessions', etc.
        analytical_keywords = ['cgpa', 'total', 'sessions', 'count', 'statistics', 'stats', 'average', 'performance', 'grade', 'below', 'above', 'less than', 'greater than', 'identify', 'show me', 'give me']
        is_analytical_query = any(keyword in user_message_lower for keyword in analytical_keywords)
        
        if not is_analytical_query and (learner_info.get('email') or learner_info.get('name') or 
            learner_info.get('user_id') or learner_info.get('first_name') or 
            learner_info.get('last_name')):
            
            learners = self.search_learners(learner_info)
            
            if not learners:
                search_terms = []
                if learner_info.get('email'): search_terms.append(f"email: {learner_info['email']}")
                if learner_info.get('name'): search_terms.append(f"name: {learner_info['name']}")
                if learner_info.get('first_name'): search_terms.append(f"first name: {learner_info['first_name']}")
                if learner_info.get('last_name'): search_terms.append(f"last name: {learner_info['last_name']}")
                if learner_info.get('user_id'): search_terms.append(f"user ID: {learner_info['user_id']}")
                
                return f"I couldn't find any learners matching your search criteria ({', '.join(search_terms)}). Please check the information and try again."
            
            if len(learners) == 1:
                # Show detailed information for single learner
                learner = learners[0]
                details = self.get_learner_details(learner['Email'], learner['Cohort #'])
                
                if not details:
                    return f"Found learner but couldn't retrieve detailed information for {learner['First Name']} {learner['Last Name']}."
                
                return self.format_learner_details(learner, details)
            else:
                # Show list of multiple learners with selection option
                response = f"**I found {len(learners)} learners matching your search:**\n\n"
                
                for i, learner in enumerate(learners[:10], 1):  # Limit to 10 results
                    response += f"**{i}. {learner['First Name']} {learner['Last Name']}**\n"
                    response += f"   📧 Email: {learner['Email']}\n"
                    response += f"   👤 User ID: {learner['User ID']}\n"
                    response += f"   🎓 Cohort: {learner['Cohort #']}\n"
                    response += f"   📊 Status: {learner['Status']}\n"
                    response += f"   ⭐ CGPA: {learner.get('Overall CGPA', 'N/A')}\n"
                    response += f"   📚 Courses Completed: {learner.get('Courses Completed', 'N/A')}/7\n"
                    response += f"   🏷️ Batch: {learner.get('Batch', 'N/A')}\n\n"
                
                response += "**Please select a learner by typing the corresponding number (1-{}) to see detailed information.**".format(min(len(learners), 10))
                
                # Store the multiple results in session context for selection
                if session_context:
                    session_context['multiple_results'] = learners[:10]
                
                return response
        
        # Cohort statistics
        elif 'cohort' in user_message_lower or 'statistics' in user_message_lower or 'stats' in user_message_lower:
            cohort_info = self.extract_learner_info(user_message)
            cohort = cohort_info.get('cohort')
            
            stats = self.get_cohort_statistics(cohort)
            
            if not stats:
                return "I couldn't find statistics for the specified cohort."
            
            if cohort:
                response = f"**Cohort {cohort} Statistics:**\n\n"
                response += f"- Total Learners: {stats.get('total_learners', 0)}\n"
                response += f"- Active Learners: {stats.get('active_learners', 0)}\n"
                response += f"- Average CGPA: {stats.get('avg_cgpa', 0):.2f}\n"
                response += f"- Completed All Courses: {stats.get('completed_all_courses', 0)}\n"
                response += f"- International Learners: {stats.get('international_learners', 0)}\n"
                response += f"- Domestic Learners: {stats.get('domestic_learners', 0)}\n"
            else:
                response = "**All Cohorts Statistics:**\n\n"
                for cohort_stat in stats:
                    response += f"**Cohort {cohort_stat['Cohort #']}:**\n"
                    response += f"- Total Learners: {cohort_stat.get('total_learners', 0)}\n"
                    response += f"- Active Learners: {cohort_stat.get('active_learners', 0)}\n"
                    response += f"- Average CGPA: {cohort_stat.get('avg_cgpa', 0):.2f}\n"
                    response += f"- Completed All Courses: {cohort_stat.get('completed_all_courses', 0)}\n\n"
            
            return response
        
        # Low performing learners
        elif any(term in user_message_lower for term in ['low grade', 'poor performance', 'failing', 'low cgpa', 'struggling']):
            cohort_info = self.extract_learner_info(user_message)
            cohort = cohort_info.get('cohort')
            
            low_performers = self.get_low_performing_learners(cohort)
            
            if not low_performers:
                return f"No learners with low grades found{' in cohort ' + cohort if cohort else ''}."
            
            response = f"**Learners with Low Grades{' - Cohort ' + cohort if cohort else ''}:**\n\n"
            for learner in low_performers:
                response += f"**{learner['name']}** (CGPA: {learner['cgpa']})\n"
                response += f"- Email: {learner['email']}\n"
                response += f"- Cohort: {learner['cohort']}\n"
                response += f"- Low Grade Courses: {', '.join(learner['low_grade_courses'])}\n\n"
            
            return response
        
        # General help
        elif any(term in user_message_lower for term in ['help', 'what can you do', 'capabilities']):
            return """**I can help you with learner information in the following ways:**

    🔍 **Search for Learners:**
    - "Show me details for John Doe"
    - "Find learner with email example@email.com"
    - "Search for user ID 1234567"
    - "Show information for Madhusudhan Tamraparni"

    📊 **Cohort Analytics:**
    - "C1 statistics"
    - "Show cohort stats"
    - "How is cohort C2 performing?"

    ⚠️ **Performance Alerts:**
    - "Show learners with low grades"
    - "Who is struggling academically?"
    - "Low performers in C3"

    🎓 **Academic Progress:**
    - "How many completed all courses?"

Just ask me anything about the learners!"""

        # ===== DEFAULT RESPONSE - USE AI FOR GENERAL QUERIES =====
        # If we reach here, use AI for general queries
        # Try to get database context for AI
        context = ""
        try:
            conn = self.get_db_connection()
            if conn:
                # Get basic stats for context
                stats_query = """
                SELECT 
                    COUNT(DISTINCT "Email") as total_students,
                    COUNT(DISTINCT "Cohort #") as total_cohorts,
                    COUNT(CASE WHEN "Status" IN ('Active', 'Active / Deferred In') THEN 1 END) as active_students
                FROM "Student List"
                """
                df = pd.read_sql_query(stats_query, conn)
                if not df.empty:
                    stats = df.iloc[0]
                    context = f"Current platform stats: {stats['total_students']} total students, {stats['active_students']} active students across {stats['total_cohorts']} cohorts."
                conn.close()
        except Exception as e:
            logger.error(f"Error getting context for AI: {e}")
        
        return self.get_ai_response(user_message, context)

    def format_learner_details(self, learner: Dict[str, Any], details: Dict[str, Any]) -> str:
        """Format detailed learner information in a consistent way"""
        response = f"**📋 Learner Details - {learner['First Name']} {learner['Last Name']}**\n\n"
        
        response += f"**👤 Personal Information:**\n"
        response += f"   📧 Email: {learner['Email']}\n"
        response += f"   🎓 Cohort: {learner['Cohort #']}\n"
        response += f"   📊 Status: {learner['Status']}\n"
        response += f"   🏷️ Batch: {learner['Batch']}\n"
        response += f"   🕒 Slot: {learner.get('Slot', 'N/A')}\n\n"
        
        if details.get('academic_info'):
            academic = details['academic_info']
            response += f"**📚 Academic Information:**\n"
            response += f"   ⭐ Overall CGPA: {academic.get('Overall CGPA', 'N/A')}\n"
            response += f"   ✅ Courses Completed: {academic.get('Courses Completed', 'N/A')}\n"
            response += f"   ❌ Courses Incomplete: {academic.get('Courses Incomplete', 'N/A')}\n\n"
            
            if details.get('courses'):
                response += f"**📖 Course Grades:**\n"
                for course in details['courses']:
                    grade_emoji = "⚠️" if course['grade'] in ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I'] else "✅"
                    response += f"   {grade_emoji} {course['name']}: {course['grade']} (Credit: {course['credit']})\n"
                response += "\n"
        
        if details.get('dissertation_info'):
            dissertation = details['dissertation_info']
            # Check if dissertation has meaningful data
            has_dissertation_data = any(
                dissertation.get(key) not in [None, 'N/A', ''] 
                for key in ['Dissertation mode', 'Chair', 'Co-Chair', 'Topic Proposal Submission']
            )
            
            if has_dissertation_data:
                response += f"**🎓 Dissertation Information:**\n"
                response += f"   📝 Mode: {dissertation.get('Dissertation mode', 'N/A')}\n"
                response += f"   👨‍🏫 Chair: {dissertation.get('Chair', 'N/A')}\n"
                response += f"   👩‍🏫 Co-Chair: {dissertation.get('Co-Chair', 'N/A')}\n"
                response += f"   📄 Topic Proposal Status: {dissertation.get('Topic Proposal Submission', 'N/A')}\n"
                response += f"   ✅ Topic Proposal Approval: {dissertation.get('Topic Proposal Approval', 'N/A')}\n"
        
        response += f"\n💡 *Need more information? Ask me about another learner or type 'help' for options.*"
        
        return response

# Initialize chatbot
chatbot = EduOpsChatbot(DB_PATH)

@chatbot_bp.route('/ask', methods=['POST'])
def ask_chatbot():
    """
    Main endpoint for chatbot queries - FIXED session management
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({'response': 'Please provide a message.'})
        
        logger.info(f"Chatbot query from session {session_id}: {user_message}")
        
        # Get or create session context - ensure it persists
        session_key = f"chatbot_context_{session_id}"
        
        # Initialize session context if it doesn't exist
        if session_key not in flask_session:
            flask_session[session_key] = {}
        
        # Get a reference to the session context
        session_context = flask_session[session_key]
        
        # Add user name to session context if available
        if 'first_name' in flask_session and 'last_name' in flask_session:
            user_name = f"{flask_session.get('first_name', '')} {flask_session.get('last_name', '')}".strip()
            session_context['user_name'] = user_name
        
        # Process the query with session context
        response = chatbot.process_query(user_message, session_context)
        flask_session.modified = True
        
        logger.info(f"Session context after processing: {session_context}")
        
        return jsonify({
            'response': response,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Error in chatbot endpoint: {e}")
        return jsonify({
            'response': 'Sorry, I encountered an error processing your request. Please try again.'
        })
        
        
@chatbot_bp.route('/api/learner-stats', methods=['GET'])
def get_learner_stats():
    """
    API endpoint to get general learner statistics
    """
    try:
        conn = chatbot.get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'})
        
        # Get overall statistics
        query = """
        SELECT 
            COUNT(DISTINCT "Email") as total_learners,
            SUM(CASE WHEN "Status" IN ('Active', 'Active / Deferred In', 'Active (Prospective Deferral)') THEN 1 ELSE 0 END) as active_learners,
            COUNT(DISTINCT "Cohort #") as total_cohorts
        FROM "Student List"
        """
        
        df = pd.read_sql_query(query, conn)
        stats = df.iloc[0].to_dict() if not df.empty else {}
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting learner stats: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

@chatbot_bp.route('/api/query-data', methods=['POST'])
def query_data():
    """
    Advanced data query endpoint
    """
    try:
        data = request.get_json()
        query_type = data.get('query_type')
        parameters = data.get('parameters', {})
        
        if query_type == 'average_cgpa':
            conn = chatbot.get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Database connection failed'})
            
            query = "SELECT AVG(\"Overall CGPA\") as avg_cgpa FROM Gradesheet WHERE \"Overall CGPA\" IS NOT NULL"
            df = pd.read_sql_query(query, conn)
            avg_cgpa = df.iloc[0]['avg_cgpa'] if not df.empty else 0
            
            return jsonify({
                'success': True,
                'result': f"{avg_cgpa:.2f}" if avg_cgpa else "N/A"
            })
        
        else:
            return jsonify({'success': False, 'error': 'Unknown query type'})
            
    except Exception as e:
        logger.error(f"Error in data query: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if 'conn' in locals() and conn:
            conn.close()