#!/usr/bin/env python3
"""
Admin management script for GPU Priority Service
Usage:
  python manage_admin.py add <username> <email>
  python manage_admin.py remove <username>
  python manage_admin.py list
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, AdminUser

def add_admin(username, email):
    """Add an admin user"""
    app = create_app()
    with app.app_context():
        existing = AdminUser.query.filter_by(username=username).first()
        if existing:
            print(f"Admin user '{username}' already exists")
            return False

        admin = AdminUser(username=username, email=email)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user '{username}' ({email}) added successfully")
        return True

def remove_admin(username):
    """Remove an admin user"""
    app = create_app()
    with app.app_context():
        admin = AdminUser.query.filter_by(username=username).first()
        if not admin:
            print(f"Admin user '{username}' not found")
            return False

        db.session.delete(admin)
        db.session.commit()
        print(f"Admin user '{username}' removed successfully")
        return True

def list_admins():
    """List all admin users"""
    app = create_app()
    with app.app_context():
        admins = AdminUser.query.all()
        if not admins:
            print("No admin users found")
            return

        print("Admin users:")
        for admin in admins:
            print(f"  - {admin.username} ({admin.email}) - added {admin.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_admin.py add <username> <email>")
        print("  python manage_admin.py remove <username>")
        print("  python manage_admin.py list")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'add':
        if len(sys.argv) != 4:
            print("Usage: python manage_admin.py add <username> <email>")
            sys.exit(1)
        username = sys.argv[2]
        email = sys.argv[3]
        add_admin(username, email)

    elif command == 'remove':
        if len(sys.argv) != 3:
            print("Usage: python manage_admin.py remove <username>")
            sys.exit(1)
        username = sys.argv[2]
        remove_admin(username)

    elif command == 'list':
        list_admins()

    else:
        print(f"Unknown command: {command}")
        print("Available commands: add, remove, list")
        sys.exit(1)

if __name__ == '__main__':
    main()
