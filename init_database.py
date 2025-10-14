#!/usr/bin/env python3
"""
Database Initialization Script for EduOps360
This script creates the necessary database tables for the application.
Run this after deployment to set up the database structure.
"""

import os
import sqlite3
from utils.database import get_db_connection

def create_tables():
    """Create all necessary database tables"""
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Users table for authentication
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
        
        # OTP codes table
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
        
        # Email campaigns tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                template_id INTEGER,
                template_content TEXT,
                recipient_list TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                completed_at TIMESTAMP,
                total_recipients INTEGER DEFAULT 0,
                emails_sent INTEGER DEFAULT 0,
                emails_failed INTEGER DEFAULT 0,
                emails_pending INTEGER DEFAULT 0,
                open_rate REAL DEFAULT 0,
                click_rate REAL DEFAULT 0,
                bounce_rate REAL DEFAULT 0,
                created_by TEXT,
                email_account TEXT,
                campaign_type TEXT DEFAULT 'bulk',
                priority INTEGER DEFAULT 1,
                tags TEXT,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT,
                html_content TEXT,
                text_content TEXT,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Attendance and ratings upload tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                session_id TEXT NOT NULL,
                attended BOOLEAN NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ratings_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                session_id TEXT NOT NULL,
                rating REAL NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by TEXT
            )
        ''')
        
        # Create default admin user
        cursor.execute('''
            INSERT OR IGNORE INTO users (email, first_name, last_name, role, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('akshit1.shetty@upgrad.com', 'Akshit', 'Shetty', 'admin', 1))
        
        conn.commit()
        print("✅ Database tables created successfully!")
        print("✅ Default admin user created: akshit1.shetty@upgrad.com")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()

def check_database_connection():
    """Check if database connection works"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        print("✅ Database connection successful!")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Initializing EduOps360 Database...")
    
    if check_database_connection():
        create_tables()
        print("🎉 Database initialization completed!")
    else:
        print("❌ Database initialization failed!")
