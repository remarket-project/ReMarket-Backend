#!/usr/bin/env python
"""Temporary script to initialize the services directory"""
from pathlib import Path

# Create services directory
services_dir = Path(__file__).parent / "app" / "services"
services_dir.mkdir(parents=True, exist_ok=True)
print(f"✅ Created directory: {services_dir}")
