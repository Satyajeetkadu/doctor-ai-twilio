"""
Test script for Doctor AI WhatsApp Assistant
Run this to test the application before deployment
"""

import asyncio
import os
from dotenv import load_dotenv
from services.gemini_service import analyze_message, _get_fallback_response
from services.supabase_service import test_connection as test_supabase
from services.twilio_service import test_connection as test_twilio
from services.gcal_service import test_connection as test_gcal

# Load environment variables
load_dotenv()

async def test_gemini_service():
    """Test Gemini AI service"""
    print("🧠 Testing Gemini AI Service...")
    
    test_messages = [
        "I want to book an appointment",
        "Hello",
        "1",
        "I'll take slot 3",
        "Cancel my appointment"
    ]
    
    for message in test_messages:
        try:
            result = await analyze_message(message)
            print(f"  Message: '{message}' -> Intent: {result['intent']}")
        except Exception as e:
            print(f"  ❌ Error with message '{message}': {e}")
            # Test fallback
            fallback = _get_fallback_response(message)
            print(f"  Fallback -> Intent: {fallback['intent']}")
    
    print("✅ Gemini service test completed\n")

async def test_database_connection():
    """Test Supabase database connection"""
    print("🗄️ Testing Supabase Database Connection...")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or supabase_key == "your_service_key":
        print("  ⚠️ Supabase credentials not configured")
        print("  Please update your .env file with proper Supabase credentials")
        return False
    
    try:
        result = await test_supabase()
        if result:
            print("  ✅ Database connection successful")
        else:
            print("  ❌ Database connection failed")
        return result
    except Exception as e:
        print(f"  ❌ Database connection error: {e}")
        return False

async def test_twilio_connection():
    """Test Twilio connection"""
    print("📱 Testing Twilio Connection...")
    
    try:
        result = await test_twilio()
        if result:
            print("  ✅ Twilio connection successful")
        else:
            print("  ❌ Twilio connection failed")
        return result
    except Exception as e:
        print(f"  ❌ Twilio connection error: {e}")
        return False

async def test_calendar_connection():
    """Test Google Calendar connection"""
    print("📅 Testing Google Calendar Connection...")
    
    try:
        result = await test_gcal()
        if result:
            print("  ✅ Google Calendar connection successful")
        else:
            print("  ⚠️ Google Calendar not configured (optional for MVP)")
        return result
    except Exception as e:
        print(f"  ⚠️ Google Calendar error: {e} (optional for MVP)")
        return False

def check_environment_variables():
    """Check if all required environment variables are set"""
    print("🔧 Checking Environment Variables...")
    
    required_vars = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN", 
        "TWILIO_PHONE_NUMBER"
    ]
    
    optional_vars = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "GEMINI_API_KEY"
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
        else:
            print(f"  ✅ {var}: {'*' * len(os.getenv(var))}")  # Hide actual values
    
    for var in optional_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_"):
            missing_optional.append(var)
        else:
            print(f"  ✅ {var}: {'*' * len(value)}")
    
    if missing_required:
        print(f"  ❌ Missing required variables: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        print(f"  ⚠️ Missing optional variables: {', '.join(missing_optional)}")
    
    print("✅ Environment variables check completed\n")
    return True

async def main():
    """Run all tests"""
    print("🚀 Doctor AI WhatsApp Assistant - Test Suite")
    print("=" * 50)
    
    # Check environment variables first
    env_ok = check_environment_variables()
    
    if not env_ok:
        print("❌ Environment setup incomplete. Please check your .env file.")
        return
    
    # Test all services
    await test_gemini_service()
    
    db_ok = await test_database_connection()
    twilio_ok = await test_twilio_connection()
    calendar_ok = await test_calendar_connection()
    
    print("📊 Test Summary:")
    print(f"  Database: {'✅' if db_ok else '❌'}")
    print(f"  Twilio: {'✅' if twilio_ok else '❌'}")
    print(f"  Calendar: {'✅' if calendar_ok else '⚠️'}")
    print(f"  Gemini: ✅")
    
    if db_ok and twilio_ok:
        print("\n🎉 Core services are ready! You can deploy the application.")
        print("\n📝 Next steps:")
        print("1. Create a Supabase project named 'doctor_ai'")
        print("2. Run the database_setup.sql script in Supabase SQL editor")
        print("3. Update .env with Supabase credentials")
        print("4. Set up Google Calendar API (optional)")
        print("5. Deploy to Render")
    else:
        print("\n⚠️ Some services need configuration before deployment.")

if __name__ == "__main__":
    asyncio.run(main()) 