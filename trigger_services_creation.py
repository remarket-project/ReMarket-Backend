#!/usr/bin/env python3
"""Trigger the services directory creation by importing app"""
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

# Import app module which will trigger the services directory creation code in __init__.py
try:
    import app
    print("✅ App module imported successfully")
    print("✅ Services directory and files created successfully!")

    # Verify the files were created
    services_dir = project_root / "app" / "services"
    if services_dir.exists():
        print(f"✅ Services directory exists: {services_dir}")
        init_file = services_dir / "__init__.py"
        email_file = services_dir / "email_service.py"

        if init_file.exists():
            print(f"✅ __init__.py created: {init_file}")
        if email_file.exists():
            print(f"✅ email_service.py created: {email_file}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
