#!/usr/bin/env python3
"""
Quick verification script to test the fixed architecture
Run this to verify all imports and service initialization works
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

print("🔧 Quick Architecture Verification")
print("=" * 40)

# Test imports
print("📦 Testing imports...")

try:
    from services.gemini_service import analyze_message, get_gemini_model
    print("  ✅ Gemini service imported successfully")
except ImportError as e:
    print(f"  ❌ Gemini service import failed: {e}")

try:
    from services.supabase_service import get_supabase_client, find_or_create_patient
    print("  ✅ Supabase service imported successfully")
except ImportError as e:
    print(f"  ❌ Supabase service import failed: {e}")

try:
    from services.twilio_service import get_twilio_client, send_whatsapp_message
    print("  ✅ Twilio service imported successfully")
except ImportError as e:
    print(f"  ❌ Twilio service import failed: {e}")

try:
    from services.gcal_service import get_calendar_service, create_calendar_event
    print("  ✅ Google Calendar service imported successfully")
except ImportError as e:
    print(f"  ❌ Google Calendar service import failed: {e}")

print("\n🔑 Testing environment variables...")

# Check key environment variables
env_vars = {
    "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
    "SUPABASE_URL": os.getenv("SUPABASE_URL"),
    "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
}

for var_name, var_value in env_vars.items():
    if var_value:
        print(f"  ✅ {var_name}: {'*' * 10}...{var_value[-4:]}")
    else:
        print(f"  ❌ {var_name}: Not set")

print("\n🔧 Testing service initialization...")

# Test lazy loading
try:
    gemini_model = get_gemini_model()
    if gemini_model:
        print("  ✅ Gemini model initialized")
    else:
        print("  ⚠️  Gemini model not initialized (API key issue)")
except Exception as e:
    print(f"  ❌ Gemini model failed: {e}")

try:
    supabase = get_supabase_client()
    if supabase:
        print("  ✅ Supabase client initialized")
    else:
        print("  ❌ Supabase client not initialized")
except Exception as e:
    print(f"  ❌ Supabase client failed: {e}")

try:
    twilio = get_twilio_client()
    if twilio:
        print("  ✅ Twilio client initialized")
    else:
        print("  ❌ Twilio client not initialized")
except Exception as e:
    print(f"  ❌ Twilio client failed: {e}")

try:
    calendar = get_calendar_service()
    if calendar:
        print("  ✅ Google Calendar service initialized")
    else:
        print("  ⚠️  Google Calendar service not configured (optional)")
except Exception as e:
    print(f"  ❌ Google Calendar service failed: {e}")

print("\n🏁 Verification complete!")
print("\nNext steps:")
print("1. If .env file is missing, create it with the provided content")  
print("2. Run: python test_app.py")
print("3. Run: uvicorn main:app --reload")
print("4. Test the /whatsapp-webhook endpoint") 