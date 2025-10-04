# chatbot.py
from flask import Blueprint, request, jsonify, session as flask_session
import sqlite3
import pandas as pd
import logging
from typing import Dict, List, Any, Optional
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)

# Database path
DB_PATH = "GGU DBA ET Learner Journey.db"

class EduOpsChatbot:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
    def get_db_connection(self):
        """Create and return a database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
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
        # Look for full name pattern (First Last)
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
            capitalized_words = [word for word in words if word.istitle() and len(word) > 1]
            
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
            course_columns = ['DBA 805 Grade', 'DBA 806 Grade', 'DBA 863 Grade', 
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
        COURSE_COLUMNS = ['DBA 805 Grade', 'DBA 806 Grade', 'DBA 863 Grade', 
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
        
        # ===== EXISTING FUNCTIONALITY =====
        # Enhanced search for specific learner
        if (learner_info.get('email') or learner_info.get('name') or 
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
    - "Show international vs domestic stats"
    - "Average CGPA by cohort"

    Just ask me anything about the learners!"""

        # Default response
        else:
            return """🤖 I'm here to help you with learner information! 

    Try asking me about:
    - A specific learner (by name, email, or user ID)
    - Cohort statistics 
    - Learners with low grades
    - Program analytics
    - Or type 'help' to see all capabilities

    For example: 
    - "Show me details for madhu.tamraparni@gmail.com" 
    - "C1 statistics"
    - "Hello, how are you?"
    - "Find John Smith"""

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
        
        # Process the query with session context
        response = chatbot.process_query(user_message, session_context)
        
        # Update the session with the modified context
        flask_session[session_key] = session_context
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