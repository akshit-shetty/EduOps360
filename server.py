#!/usr/bin/env python3
"""
Production server entry point for EduOps360
Optimized for cloud deployment platforms like Appwrite, Render, Heroku
"""

import os
import sys
import logging
from werkzeug.middleware.proxy_fix import ProxyFix

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main Flask application
from app import app

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Apply ProxyFix for proper handling behind reverse proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

def create_app():
    """
    Application factory for production deployment
    """
    # Set production environment variables
    os.environ.setdefault('FLASK_ENV', 'production')
    
    # Test database connection
    try:
        from utils.database import get_db_connection
        conn = get_db_connection()
        conn.close()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    logger.info("✅ EduOps360 application initialized successfully")
    return app

# Create the application instance
application = create_app()

if __name__ == '__main__':
    # Get port from environment (Appwrite uses PORT environment variable)
    port = int(os.environ.get('PORT', 3000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"🚀 Starting EduOps360 server on {host}:{port}")
    logger.info(f"🔧 Debug mode: {debug}")
    logger.info(f"🌍 Environment: {os.environ.get('FLASK_ENV', 'production')}")
    
    try:
        application.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)
