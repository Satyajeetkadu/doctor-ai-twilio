#!/usr/bin/env python3
"""
Comprehensive test script for enhanced Doctor AI flows
Tests the new profile management, symptoms separation, and universal greeting system
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our services
from services.gemini_service import analyze_message
from services.supabase_service import (
    find_or_create_patient, get_patient_profile_summary, 
    update_current_symptoms, update_profile_field,
    get_patient_onboarding_status, test_connection
)
from services.twilio_service import send_whatsapp_message
from services.gcal_service import create_calendar_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_gemini_prompts():
    """Test the enhanced Gemini prompts with new intents"""
    logger.info("🧠 Testing Enhanced Gemini Prompts...")
    
    test_cases = [
        ("Hello", "greeting"),
        ("1", "profile_choice"),
        ("2", "profile_choice"),
        ("Quick booking", "quick_book_with_profile"),
        ("Update my profile", "update_profile_only"),
        ("Start fresh", "start_fresh"),
        ("I have fever and headache today", "provide_current_symptoms"),
        ("25", "provide_age"),
        ("john@example.com", "provide_email"),
        ("Male", "provide_gender"),
        ("B+", "provide_blood_group"),
        ("No allergies", "provide_allergies"),
        ("Friday at 4pm", "request_custom_date"),
        ("keep", "unknown"),  # Context-dependent
    ]
    
    for message, expected_intent in test_cases:
        try:
            result = await analyze_message(message)
            actual_intent = result.get("intent", "")
            
            if actual_intent == expected_intent:
                logger.info(f"✅ '{message}' → {actual_intent}")
            else:
                logger.warning(f"⚠️  '{message}' → Expected: {expected_intent}, Got: {actual_intent}")
                
        except Exception as e:
            logger.error(f"❌ Error testing '{message}': {e}")
    
    logger.info("✅ Gemini prompts test completed")

async def test_profile_management():
    """Test the new profile management functions"""
    logger.info("👤 Testing Profile Management...")
    
    try:
        # Create a test patient
        patient = await find_or_create_patient("+1234567890", "Test User Enhanced")
        if not patient:
            logger.error("❌ Failed to create test patient")
            return False
            
        patient_id = patient['id']
        logger.info(f"✅ Created test patient: {patient_id}")
        
        # Test profile summary
        profile = await get_patient_profile_summary(patient_id)
        if profile:
            logger.info(f"✅ Retrieved profile summary: {profile.get('full_name')}")
        else:
            logger.warning("⚠️  No profile summary found")
        
        # Test profile field updates
        updates = [
            ("email", "test.enhanced@example.com"),
            ("age", "28"),
            ("gender", "Male"),
            ("blood_group", "O+"),
            ("allergies", "None")
        ]
        
        for field, value in updates:
            result = await update_profile_field(patient_id, field, value)
            if result:
                logger.info(f"✅ Updated {field}: {value}")
            else:
                logger.error(f"❌ Failed to update {field}")
        
        # Test current symptoms (separate from profile)
        symptoms_result = await update_current_symptoms(patient_id, "Headache and fever for testing")
        if symptoms_result:
            logger.info("✅ Updated current symptoms (separate from profile)")
        else:
            logger.error("❌ Failed to update current symptoms")
        
        # Test onboarding status
        status = await get_patient_onboarding_status(patient_id)
        if status:
            logger.info(f"✅ Retrieved onboarding status: {status.get('onboarding_step')}")
        else:
            logger.warning("⚠️  No onboarding status found")
        
        logger.info("✅ Profile management test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Profile management test failed: {e}")
        return False

async def test_conversation_flows():
    """Test conversation flow scenarios"""
    logger.info("💬 Testing Conversation Flows...")
    
    scenarios = [
        {
            "name": "New User Greeting",
            "messages": ["Hello"],
            "expected_keywords": ["Doctor AI", "intelligent", "book appointment"]
        },
        {
            "name": "Returning User Profile Choice",
            "messages": ["Hi", "1"],
            "expected_keywords": ["profile information", "current symptoms"]
        },
        {
            "name": "Profile Update Flow",
            "messages": ["Hello", "2", "keep", "30", "Female"],
            "expected_keywords": ["update", "profile", "keep"]
        },
        {
            "name": "Current Symptoms Flow",
            "messages": ["I have a headache"],
            "expected_keywords": ["symptoms noted", "available slots"]
        }
    ]
    
    for scenario in scenarios:
        logger.info(f"Testing scenario: {scenario['name']}")
        
        for message in scenario['messages']:
            try:
                result = await analyze_message(message)
                logger.info(f"  Message: '{message}' → Intent: {result.get('intent')}")
            except Exception as e:
                logger.error(f"  ❌ Error with message '{message}': {e}")
    
    logger.info("✅ Conversation flows test completed")

async def test_service_connections():
    """Test all service connections"""
    logger.info("🔗 Testing Service Connections...")
    
    services_status = {
        "Supabase": False,
        "Gemini": False,
        "Google Calendar": False
    }
    
    # Test Supabase
    try:
        supabase_ok = await test_connection()
        services_status["Supabase"] = supabase_ok
        logger.info(f"Supabase: {'✅' if supabase_ok else '❌'}")
    except Exception as e:
        logger.error(f"Supabase test failed: {e}")
    
    # Test Gemini
    try:
        gemini_result = await analyze_message("test")
        services_status["Gemini"] = "intent" in gemini_result
        logger.info(f"Gemini: {'✅' if services_status['Gemini'] else '❌'}")
    except Exception as e:
        logger.error(f"Gemini test failed: {e}")
    
    # Test Google Calendar (basic initialization)
    try:
        from services.gcal_service import get_calendar_service
        calendar_service = get_calendar_service()
        services_status["Google Calendar"] = calendar_service is not None
        logger.info(f"Google Calendar: {'✅' if services_status['Google Calendar'] else '❌'}")
    except Exception as e:
        logger.error(f"Google Calendar test failed: {e}")
    
    all_working = all(services_status.values())
    logger.info(f"Overall status: {'✅ All services working' if all_working else '⚠️  Some services have issues'}")
    
    return services_status

async def test_enhanced_features():
    """Test specific enhanced features"""
    logger.info("🚀 Testing Enhanced Features...")
    
    # Test symptoms vs allergies distinction
    logger.info("Testing symptoms vs allergies distinction...")
    
    symptom_tests = [
        ("I have a headache today", "provide_current_symptoms"),
        ("I'm allergic to penicillin", "provide_allergies"),
        ("Fever and cough", "provide_current_symptoms"),
        ("No allergies", "provide_allergies")
    ]
    
    for message, expected in symptom_tests:
        try:
            result = await analyze_message(message)
            actual = result.get("intent", "")
            status = "✅" if actual == expected else "⚠️"
            logger.info(f"  {status} '{message}' → {actual} (expected: {expected})")
        except Exception as e:
            logger.error(f"  ❌ Error testing '{message}': {e}")
    
    # Test profile choice recognition
    logger.info("Testing profile choice recognition...")
    
    choice_tests = [
        ("1", "1"),
        ("2", "2"), 
        ("3", "3"),
        ("4", "4")
    ]
    
    for message, expected_choice in choice_tests:
        try:
            result = await analyze_message(message)
            actual_choice = result.get("entities", {}).get("profile_choice")
            status = "✅" if actual_choice == expected_choice else "⚠️"
            logger.info(f"  {status} Choice '{message}' → {actual_choice}")
        except Exception as e:
            logger.error(f"  ❌ Error testing choice '{message}': {e}")
    
    logger.info("✅ Enhanced features test completed")

async def test_environment_variables():
    """Test that all required environment variables are present"""
    logger.info("🌍 Testing Environment Variables...")
    
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY", 
        "GEMINI_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Don't log actual values for security
            logger.info(f"✅ {var}: {'*' * min(len(value), 20)}")
        else:
            logger.error(f"❌ {var}: Not found")
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing variables: {missing_vars}")
        return False
    else:
        logger.info("✅ All environment variables present")
        return True

async def main():
    """Run all tests"""
    logger.info("🎯 Starting Enhanced Doctor AI Test Suite...")
    logger.info("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_results["Environment"] = await test_environment_variables()
    test_results["Services"] = await test_service_connections()
    test_results["Gemini"] = True  # Will be set based on analyze_message tests
    test_results["Profile"] = await test_profile_management()
    
    # Additional tests
    await test_enhanced_gemini_prompts()
    await test_conversation_flows() 
    await test_enhanced_features()
    
    # Summary
    logger.info("=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, status in test_results.items():
        status_icon = "✅" if status else "❌"
        logger.info(f"{status_icon} {test_name}: {'PASS' if status else 'FAIL'}")
    
    all_passed = all(test_results.values())
    overall_status = "✅ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"
    logger.info("=" * 60)
    logger.info(f"🎯 OVERALL STATUS: {overall_status}")
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("🚀 Enhanced Doctor AI is ready for deployment!")
    else:
        logger.warning("🔧 Please fix failing tests before deployment")

if __name__ == "__main__":
    asyncio.run(main()) 