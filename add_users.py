# add_users.py
import sqlite3
import hashlib
import secrets

def create_user_table():
    """Create users table if it doesn't exist"""
    conn = sqlite3.connect("GGU DBA ET Learner Journey.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()

def add_name_columns_if_missing():
    """Add first_name and last_name columns if they don't exist"""
    conn = sqlite3.connect("GGU DBA ET Learner Journey.db")
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'first_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    if 'last_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(first_name, last_name, email, password, role='user'):
    """Add a new user, or update if user already exists"""
    password_hash = hash_password(password)
    
    conn = sqlite3.connect("GGU DBA ET Learner Journey.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (first_name, last_name, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (first_name, last_name, email, password_hash, role))
        
        conn.commit()
        print(f"\n✅ User created successfully!")
        print(f"Name: {first_name} {last_name}")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: {role}")
    
    except sqlite3.IntegrityError:
        print(f"\n⚠️ User with email {email} already exists.")
        choice = input("Do you want to update this user? (yes/no): ").strip().lower()
        if choice in ["yes", "y"]:
            cursor.execute('''
                UPDATE users
                SET first_name = ?, last_name = ?, password_hash = ?, role = ?
                WHERE email = ?
            ''', (first_name, last_name, password_hash, role, email))
            conn.commit()
            print(f"\n🔄 User updated successfully!")
            print(f"Name: {first_name} {last_name}")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print(f"Role: {role}")
        else:
            print("❌ User not updated.")
    
    conn.close()

if __name__ == "__main__":
    create_user_table()
    add_name_columns_if_missing()
    
    print("Enter user details to add a new user:\n")
    first_name = input("First Name: ").strip()
    last_name = input("Last Name: ").strip()
    email = input("Email: ").strip()
    role = input("Role (default 'user'): ").strip() or 'user'
    password = input("Password (leave blank to generate randomly): ").strip()
    
    if not password:
        # Generate random password if not provided
        password = secrets.token_urlsafe(12)
    
    add_user(first_name, last_name, email, password, role)
