import os
import json
from dotenv import load_dotenv
from services.gcal_service import get_calendar_service

print("🧪 Testing Google Calendar Integration...")

load_dotenv()

# Check if environment variable exists
google_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
if google_json:
    print("✅ GOOGLE_SERVICE_ACCOUNT_JSON found in environment")
    try:
        # Test JSON parsing
        parsed = json.loads(google_json)
        print("✅ JSON parses correctly")
        print(f"✅ Project ID: {parsed.get('project_id')}")
        print(f"✅ Client Email: {parsed.get('client_email')}")
        
        # Test calendar service initialization
        print("\n🔧 Testing calendar service initialization...")
        calendar_service = get_calendar_service()
        if calendar_service:
            print("✅ Google Calendar service initialized successfully!")
            print("🎉 Calendar integration is now working!")
        else:
            print("❌ Calendar service failed to initialize")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
else:
    print("❌ GOOGLE_SERVICE_ACCOUNT_JSON not found")
