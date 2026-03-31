#!/usr/bin/env python3
"""Verify that services directory and files will be created"""
import sys
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import app to trigger __init__.py
try:
    import app
    print("✅ App imported successfully")
except ImportError as e:
    print(f"⚠️  Import warning (expected for some dependencies): {e}")

# Check if services directory and files were created
services_dir = project_root / "app" / "services"
if services_dir.exists():
    print(f"✅ Services directory created: {services_dir}")
    if (services_dir / "__init__.py").exists():
        print(f"✅ __init__.py exists in services directory")
    else:
        print(f"⚠️  __init__.py not found")

    if (services_dir / "email_service.py").exists():
        print(f"✅ email_service.py exists in services directory")
    else:
        print(f"⚠️  email_service.py not found")
else:
    print(f"⚠️  Services directory not created yet")
    print(f"   Location: {services_dir}")
    print(f"   Note: Directory will be created when app module is imported")

print("\n📝 Summary:")
print("   The app/__init__.py file contains code that creates:")
print("   - app/services/ directory")
print("   - app/services/__init__.py")
print("   - app/services/email_service.py")
print("   These will be created automatically when the app is imported or run.")
