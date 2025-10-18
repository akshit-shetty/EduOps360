#!/usr/bin/env python3

"""
WSGI Configuration for PythonAnywhere Deployment
Copy this content to your WSGI configuration file in PythonAnywhere dashboard
"""

import sys
import os

# Add your project directory to Python path
# Replace 'yourusername' with your actual PythonAnywhere username
project_home = '/home/yourusername/EduOps360'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables (optional - you can also use .env file)
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = 'False'

# Import your Flask application
from app import app as application

# For debugging (remove in production)
if __name__ == '__main__':
    application.run(debug=False)
