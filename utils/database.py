"""
Database utility functions for SQLite
Restored SQLite functionality
"""

import sqlite3
from contextlib import contextmanager
import logging
import os
from config.config import Config

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get SQLite database connection"""
    try:
        db_path = Config.DATABASE_PATH
        # Ensure the database file exists in the project directory
        if not os.path.isabs(db_path):
            # Make path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(project_root, db_path)
        
        # Ensure database file exists
        if not os.path.exists(db_path):
            logger.error(f"Database file not found at {db_path}")
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database operation error: {e}")
        raise
    finally:
        if conn:
            cursor.close()
            conn.close()

def execute_query(query, params=None, fetch=False):
    """Execute a single query"""
    with get_db_cursor() as cursor:
        cursor.execute(query, params or ())
        if fetch:
            if fetch == 'one':
                row = cursor.fetchone()
                return dict(row) if row else None
            elif fetch == 'all':
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        return cursor.rowcount

def execute_many(query, params_list):
    """Execute query with multiple parameter sets"""
    with get_db_cursor() as cursor:
        cursor.executemany(query, params_list)
        return cursor.rowcount

def table_exists(table_name):
    """Check if table exists in SQLite"""
    query = """
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name=?;
    """
    result = execute_query(query, (table_name,), fetch='one')
    return result is not None

def create_table_if_not_exists(table_name, create_sql):
    """Create table if it doesn't exist"""
    if not table_exists(table_name):
        execute_query(create_sql)
        logger.info(f"Created table: {table_name}")
    else:
        logger.info(f"Table already exists: {table_name}")
