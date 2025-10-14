#!/usr/bin/env python3
"""
EduOps360 User Management System
Comprehensive user management for the application
"""

import sqlite3
import sys
import os
from datetime import datetime

# Database configuration
DB_PATH = "eduops360.db"

class UserManager:
    """Comprehensive user management class"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.ensure_database_setup()
    
    def ensure_database_setup(self):
        """Ensure database and tables are properly set up"""
        self.create_user_table()
        self.add_name_columns_if_missing()
    
    def create_user_table(self):
        """Create users table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
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
    
    def add_name_columns_if_missing(self):
        """Add first_name and last_name columns if they don't exist"""
        conn = sqlite3.connect(self.db_path)
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
    
    def add_user(self, first_name, last_name, email, role='user', auto_update=False):
        """Add a new user (OTP-based authentication, no password needed)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (first_name, last_name, email, role)
                VALUES (?, ?, ?, ?)
            ''', (first_name, last_name, email, role))
            
            conn.commit()
            print(f"\n✅ User created successfully!")
            print(f"Name: {first_name} {last_name}")
            print(f"Email: {email}")
            print(f"Role: {role}")
            print("🔐 Authentication: OTP-based (no password required)")
            return True
        
        except sqlite3.IntegrityError:
            print(f"\n⚠️ User with email {email} already exists.")
            
            if auto_update:
                # Automatically update existing user
                cursor.execute('''
                    UPDATE users
                    SET first_name = ?, last_name = ?, role = ?
                    WHERE email = ?
                ''', (first_name, last_name, role, email))
                conn.commit()
                print(f"\n🔄 User updated successfully!")
                print(f"Name: {first_name} {last_name}")
                print(f"Email: {email}")
                print(f"Role: {role}")
                return True
            else:
                # Ask for confirmation
                choice = input("Do you want to update this user? (yes/no): ").strip().lower()
                if choice in ["yes", "y"]:
                    cursor.execute('''
                        UPDATE users
                        SET first_name = ?, last_name = ?, role = ?
                        WHERE email = ?
                    ''', (first_name, last_name, role, email))
                    conn.commit()
                    print(f"\n🔄 User updated successfully!")
                    print(f"Name: {first_name} {last_name}")
                    print(f"Email: {email}")
                    print(f"Role: {role}")
                    return True
                else:
                    print("❌ User not updated.")
                    return False
        
        finally:
            conn.close()
    
    def list_users(self):
        """List all users in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, first_name, last_name, email, role, created_at, is_active
            FROM users
            ORDER BY created_at DESC
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            print("\n📭 No users found in the database.")
            return
        
        print(f"\n👥 Users in Database ({len(users)} total):")
        print("-" * 80)
        print(f"{'ID':<4} {'Name':<25} {'Email':<30} {'Role':<10} {'Active':<8}")
        print("-" * 80)
        
        for user in users:
            user_id, first_name, last_name, email, role, created_at, is_active = user
            name = f"{first_name or ''} {last_name or ''}".strip() or "N/A"
            active_status = "Yes" if is_active else "No"
            print(f"{user_id:<4} {name:<25} {email:<30} {role:<10} {active_status:<8}")
    
    def delete_user(self, email):
        """Delete a user by email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT first_name, last_name FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"\n❌ User with email {email} not found.")
            conn.close()
            return False
        
        # Confirm deletion
        first_name, last_name = user
        name = f"{first_name or ''} {last_name or ''}".strip() or "Unknown"
        
        confirm = input(f"\n⚠️ Are you sure you want to delete user '{name}' ({email})? (yes/no): ").strip().lower()
        
        if confirm in ["yes", "y"]:
            cursor.execute("DELETE FROM users WHERE email = ?", (email,))
            conn.commit()
            print(f"\n🗑️ User '{name}' deleted successfully.")
            conn.close()
            return True
        else:
            print("❌ User deletion cancelled.")
            conn.close()
            return False
    
    def setup_default_admin(self):
        """Set up default admin user"""
        print("\n📊 Setting up default admin user...")
        
        success = self.add_user(
            first_name="Admin",
            last_name="User", 
            email="admin@eduops360.com",
            role="admin",
            auto_update=True
        )
        
        if success:
            print("\n🎉 Admin user setup completed!")
            print("You can now login to the application with:")
            print("Email: admin@eduops360.com")
            print("🔐 Authentication: OTP will be sent to your email")
            print("\n💡 Make sure your email settings are configured!")
        
        return success

def interactive_menu():
    """Interactive menu for user management"""
    user_manager = UserManager()
    
    while True:
        print("\n" + "="*50)
        print("🔐 EduOps360 User Management System")
        print("="*50)
        print("1. Add New User")
        print("2. List All Users")
        print("3. Delete User")
        print("4. Setup Default Admin")
        print("5. Exit")
        print("-"*50)
        
        choice = input("Select an option (1-5): ").strip()
        
        if choice == "1":
            print("\n📝 Add New User")
            print("-" * 20)
            first_name = input("First Name: ").strip()
            last_name = input("Last Name: ").strip()
            email = input("Email: ").strip()
            role = input("Role (user/admin) [default: user]: ").strip() or 'user'
            
            if email:
                user_manager.add_user(first_name, last_name, email, role)
            else:
                print("❌ Email is required!")
        
        elif choice == "2":
            user_manager.list_users()
        
        elif choice == "3":
            print("\n🗑️ Delete User")
            print("-" * 15)
            email = input("Enter email of user to delete: ").strip()
            if email:
                user_manager.delete_user(email)
            else:
                print("❌ Email is required!")
        
        elif choice == "4":
            password = input("Enter admin password [default: admin123]: ").strip() or "admin123"
            user_manager.setup_default_admin(password)
        
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("\n❌ Invalid choice. Please select 1-5.")

def main():
    """Main function with command line argument support"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        user_manager = UserManager()
        
        if command == "setup-admin":
            # Non-interactive admin setup
            user_manager.setup_default_admin()
        
        elif command == "list":
            # List all users
            user_manager.list_users()
        
        elif command == "add":
            # Quick add user (requires parameters)
            if len(sys.argv) >= 6:
                first_name, last_name, email, role = sys.argv[2:6]
                user_manager.add_user(first_name, last_name, email, role, auto_update=True)
            else:
                print("Usage: python user_management.py add <first_name> <last_name> <email> <role>")
        
        else:
            print("Available commands:")
            print("  setup-admin            - Setup default admin user")
            print("  list                   - List all users")
            print("  add <details>          - Add user with details")
            print("  (no command)           - Interactive menu")
    
    else:
        # Interactive mode
        interactive_menu()

if __name__ == "__main__":
    main()
