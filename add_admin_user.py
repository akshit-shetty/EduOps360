# add_admin_user.py - Non-interactive version to add admin user
import sqlite3
import hashlib
import secrets
import bcrypt

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
    """Hash password using bcrypt for security"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
        return True
    
    except sqlite3.IntegrityError:
        print(f"\n⚠️ User with email {email} already exists.")
        # Auto-update existing user
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
        return True
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 Setting up user database...")
    create_user_table()
    add_name_columns_if_missing()
    
    # Add default admin user
    print("\n📊 Adding default admin user...")
    admin_password = "admin123"  # You can change this
    
    success = add_user(
        first_name="Admin",
        last_name="User", 
        email="admin@eduops360.com",
        password=admin_password,
        role="admin"
    )
    
    if success:
        print("\n🎉 Admin user setup completed!")
        print("You can now login to the application with:")
        print("Email: admin@eduops360.com")
        print("Password: admin123")
        print("\n⚠️ Remember to change the password after first login!")
    
    print("\n✅ Database setup complete!")
