#!/usr/bin/env python3
"""
Startup script for EduOps360 - Initializes database tables if needed
"""

import os
import logging
from utils.database import get_db_connection, execute_query

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize database with essential tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create OTP codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create admin user if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO users (email, first_name, last_name, role, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('akshit1.shetty@upgrad.com', 'Akshit', 'Shetty', 'admin', 1))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = initialize_database()
    if success:
        print("✅ Database initialization completed")
    else:
        print("❌ Database initialization failed")
        exit(1)
