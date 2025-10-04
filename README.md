# EduOps360 - Educational Operations Management System

A comprehensive web application for managing educational operations, learner data, and administrative tasks for the GGU DBA ET program.

## 🚀 Features

### Core Functionality
- **Dashboard Analytics**: Real-time learner statistics and performance metrics
- **Learner Management**: Comprehensive learner profiles and progress tracking
- **Document Generation**: Automated document creation and management
- **Email Automation**: Bulk email sending with templates and scheduling
- **Folder Management**: Automated folder structure creation
- **AI Chatbot**: Intelligent query handling for learner information
- **Reminder System**: Automated session reminders for professors
- **User Authentication**: Secure login system with role-based access

### Key Modules
1. **Dashboard** (`app.py`) - Main application and analytics
2. **Document & Email** (`document_and_email.py`) - Document generation and email automation
3. **Reminder System** (`reminder.py`) - Session reminder management
4. **Folder Creator** (`create_folders.py`) - Automated folder structure creation
5. **Chatbot** (`chatbot.py`) - AI-powered query assistant
6. **Database Management** (`db.py`) - Excel to SQLite conversion
7. **User Management** (`add_users.py`) - User account management
## 🛠️ Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript, Tailwind CSS
- **Document Processing**: python-docx
- **Date/Time Processing**: python-dateutil
- **Email Integration**: Windows Outlook (win32com)
- **Authentication**: Custom session-based auth with bcrypt
- **Deployment**: Gunicorn (Production), Windows Server

## 📋 Prerequisites

- **Windows Operating System** (Required for Outlook integration)
- Python 3.8 or higher
- pip (Python package installer)
- Microsoft Outlook installed and configured
- Modern web browser

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd EduOps360/Ver11
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the root directory:
```env
FLASK_SECRET_KEY=your-super-secure-secret-key-here
FLASK_ENV=development
FLASK_DEBUG=True
DATABASE_URL=sqlite:///GGU DBA ET Learner Journey.db
SESSION_TIMEOUT_HOURS=24
```

**Note**: No SMTP configuration needed as the application uses Windows Outlook integration.

### 5. Database Setup
```bash
# Convert Excel data to SQLite (if you have the Excel file)
python db.py

# Create user accounts
python add_users.py
```

### 6. Run the Application
```bash
# Development
python app.py

# Production
gunicorn app:app
```

The application will be available at `http://localhost:5000`

## 📊 Database Structure

The application uses SQLite with the following main tables:
- **users** - User authentication and roles
- **Gradesheet** - Student grades and academic progress
- **Student List** - Learner information and enrollment data
- **Dissertation** - Dissertation phase tracking (optional)

## 🔐 Security Features

- **Secure Authentication**: bcrypt password hashing
- **Session Management**: Secure session handling with configurable timeout
- **Role-Based Access**: Admin and user role separation
- **Environment Variables**: Sensitive data stored in `.env` file
- **Input Validation**: Form data validation and sanitization

## 👥 User Roles

### Admin Users
- Full system access
- User management capabilities
- Database upload permissions
- All module access

### Regular Users
- Dashboard access
- Learner data viewing
- Limited administrative functions

## 🚀 Deployment

### Local Development
```bash
python app.py
```

### Production (Windows Server)
The application is configured for Windows Server deployment with:
- `gunicorn` - Production WSGI server
- Windows Outlook integration
- Environment variables for configuration

**Important**: This application requires Windows OS due to Outlook integration and cannot be deployed on Linux-based cloud platforms like Render, Heroku, etc.

### Environment Variables for Production
```env
FLASK_SECRET_KEY=<secure-random-key>
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=<production-database-url>
```

## 📁 Project Structure

```
EduOps360/Ver11/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── render.yaml           # Deployment configuration
├── .env                  # Environment variables (create this)
├── .gitignore           # Git ignore rules
├── README.md            # This file
├── db.py                # Database utilities
├── add_users.py         # User management script
├── chatbot.py           # AI chatbot module
├── create_folders.py    # Folder creation module
├── document_and_email.py # Document and email module
├── reminder.py          # Reminder system module
└── templates/           # HTML templates
    ├── base.html        # Base template
    ├── dashboard.html   # Main dashboard
    ├── learners.html    # Learner management
    ├── login.html       # Authentication
    └── ...              # Other templates
```

## 🔄 Data Flow

1. **Excel Upload** → SQLite conversion via `db.py`
2. **User Authentication** → Session management
3. **Dashboard** → Real-time analytics from database
4. **Document Generation** → Template-based document creation
5. **Email System** → Bulk email with tracking
6. **Chatbot** → Natural language query processing

## 🛡️ Security Considerations

- Change default secret key in production
- Use HTTPS in production
- Regularly update dependencies
- Implement proper backup strategies
- Monitor application logs

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Ensure SQLite database file exists
   - Check file permissions

2. **Import Errors**
   - Verify all dependencies are installed
   - Check Python version compatibility

3. **Authentication Issues**
   - Verify user accounts exist in database
   - Check password hashing implementation

4. **Template Not Found**
   - Ensure templates directory exists
   - Check template file names

## 📝 API Endpoints

### Authentication
- `GET /login` - Login page
- `POST /login` - User authentication
- `GET /logout` - User logout

### Dashboard
- `GET /` - Main dashboard
- `GET /learners` - Learner management
- `POST /upload_database` - Database upload

### Admin
- `GET /admin/users` - User management
- `POST /admin/add-user` - Add new user
- `POST /admin/toggle-user/<id>` - Toggle user status

### Modules
- `/document/*` - Document generation endpoints
- `/reminder/*` - Reminder system endpoints
- `/folders/*` - Folder creation endpoints
- `/chatbot/*` - Chatbot endpoints

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is proprietary software for educational institution use.

## 📞 Support

For technical support or questions, please contact the development team.

---

**Version**: 11.0  
**Last Updated**: October 2024  
**Developed for**: GGU DBA ET Program Management
