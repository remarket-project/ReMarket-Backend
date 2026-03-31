import sys
sys.path.insert(0, '.')
try:
    import app
    print("✅ App imported successfully - services directory created")
except Exception as e:
    print(f"⚠️ Error: {e}")
