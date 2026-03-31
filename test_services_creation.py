#!/usr/bin/env python3
"""
Test script to verify services directory creation.
This file demonstrates how the services directory will be created
when the app is imported (which happens when you run the application).
"""
import sys
from pathlib import Path

print("=" * 70)
print("Testing Services Directory Creation")
print("=" * 70)

# Check current status before import
services_dir = Path(__file__).parent / "app" / "services"
print(f"\n📁 Services directory location: {services_dir}")
print(f"   Exists before import: {services_dir.exists()}")

# The app/db/__init__.py file contains code that will create the directory when imported
# Let's simulate that by directly running the code
print("\n🚀 Simulating app import (which triggers app/db/__init__.py)...")

try:
    # This will execute the directory creation code in app/db/__init__.py
    from app.db import get_db
    print("✅ app.db imported successfully")
except Exception as e:
    print(
        f"⚠️  Import error (expected if database config is missing): {type(e).__name__}")
    # Even if import fails, the directory creation code in app/db/__init__.py should have run
    # Let's check:

# Check if services directory was created
print(f"\n📁 Services directory exists after import: {services_dir.exists()}")

if services_dir.exists():
    print(f"   ✅ Directory created successfully!")

    # Check for __init__.py
    init_file = services_dir / "__init__.py"
    if init_file.exists():
        print(f"   ✅ __init__.py exists")
    else:
        print(f"   ⚠️  __init__.py not found")

    # Check for email_service.py
    email_file = services_dir / "email_service.py"
    if email_file.exists():
        print(f"   ✅ email_service.py exists")
        file_size = email_file.stat().st_size
        print(f"      File size: {file_size} bytes")
    else:
        print(f"   ⚠️  email_service.py not found")
else:
    print(f"   ⚠️  Directory not created")
    print(f"   This can happen if:")
    print(f"   - Database config is invalid (prevents import)")
    print(f"   - The app hasn't been run yet")

print("\n" + "=" * 70)
print("Summary:")
print("=" * 70)
print("""
The code to create the services directory is embedded in:
  - app/db/__init__.py (will run on app startup)
  - app/__init__.py (will run when app module is imported)
  - app/main.py (will run when main.py is imported)
  - app/backend_pre_start.py (will run in Docker)

When you start the application (with 'fastapi run', 'uvicorn', etc.),
the services directory will be automatically created.

To manually create it now, run:
  python setup_services.py
""")
print("=" * 70)
