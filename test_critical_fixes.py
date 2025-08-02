#!/usr/bin/env python3
"""
Critical Fixes Validation Test
Tests the specific issues that were causing system failures:
1. Gemini 2.5 Flash JSON parsing issues
2. "Other" being stored as symptoms
3. Numbers confused between slot selection and profile choices
4. Context loss and infinite loops
5. Symptom data corruption prevention
"""

import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from services.gemini_service import analyze_message
from services.supabase_service import (
    find_or_create_patient, 
    get_patient_onboarding_status,
    update_patient_onboarding_step,
    get_patient_profile_summary
)

class CriticalFixesTester:
    def __init__(self):
        self.test_phone = "+1234567890"
        self.patient_id = None
        self.test_results = []
        
    def log_test(self, test_name, passed, details=""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   💬 {details}")
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        print()
    
    async def setup_test_patient(self):
        """Create test patient for consistent testing"""
        print("🔧 Setting up test patient...")
        patient = await find_or_create_patient(self.test_phone, "Test Patient")
        if patient:
            self.patient_id = patient['id']
            print(f"   👤 Patient ID: {self.patient_id}")
            return True
        return False
    
    async def test_gemini_json_parsing_stability(self):
        """Test 1: Gemini 2.5 Flash JSON parsing with retry logic"""
        print("🧪 Test 1: Gemini JSON Parsing Stability")
        print("-" * 40)
        
        test_messages = [
            "Hello",
            "Other", 
            "3",
            "Tomorrow at 5pm",
            "Headache",
            "Keep"
        ]
        
        all_passed = True
        
        for message in test_messages:
            try:
                analysis = await analyze_message(message, current_step="current_symptoms", is_onboarding_complete=True)
                
                # Check if we got a valid response structure
                has_intent = 'intent' in analysis
                has_entities = 'entities' in analysis and isinstance(analysis['entities'], dict)
                
                if has_intent and has_entities:
                    self.log_test(f"JSON parsing for '{message}'", True, f"Intent: {analysis['intent']}")
                else:
                    self.log_test(f"JSON parsing for '{message}'", False, f"Invalid structure: {analysis}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"JSON parsing for '{message}'", False, f"Exception: {str(e)}")
                all_passed = False
        
        return all_passed
    
    async def test_context_aware_intent_detection(self):
        """Test 2: Context-aware intent detection (numbers in different contexts)"""
        print("🧪 Test 2: Context-Aware Intent Detection")
        print("-" * 40)
        
        test_cases = [
            {
                "message": "3",
                "context": "current_symptoms",
                "onboarding_complete": True,
                "expected_intent": "select_slot",
                "description": "Number '3' in symptoms context should be slot selection"
            },
            {
                "message": "3", 
                "context": "start",
                "onboarding_complete": True,
                "expected_intent": "profile_choice",
                "description": "Number '3' in greeting context should be profile choice"
            },
            {
                "message": "25",
                "context": "age", 
                "onboarding_complete": False,
                "expected_intent": "provide_age",
                "description": "Number '25' in age context should be age input"
            }
        ]
        
        all_passed = True
        
        for case in test_cases:
            analysis = await analyze_message(
                case["message"],
                current_step=case["context"],
                is_onboarding_complete=case["onboarding_complete"]
            )
            
            actual_intent = analysis.get("intent")
            expected_intent = case["expected_intent"]
            
            passed = actual_intent == expected_intent
            if not passed:
                all_passed = False
                
            self.log_test(
                f"Context test: {case['description']}", 
                passed,
                f"Expected: {expected_intent}, Got: {actual_intent}"
            )
        
        return all_passed
    
    async def test_other_as_custom_date_not_symptoms(self):
        """Test 3: "Other" should be custom date request, not stored as symptoms"""
        print("🧪 Test 3: 'Other' Handling (Critical Bug Fix)")
        print("-" * 40)
        
        test_cases = [
            "Other",
            "other", 
            "different",
            "custom timing",
            "Tomorrow at 5pm"
        ]
        
        all_passed = True
        
        for message in test_cases:
            analysis = await analyze_message(message, current_step="current_symptoms", is_onboarding_complete=True)
            
            intent = analysis.get("intent")
            current_symptoms = analysis.get("entities", {}).get("current_symptoms")
            
            # Critical: These should NEVER be classified as symptoms
            if intent == "provide_current_symptoms" or current_symptoms is not None:
                self.log_test(
                    f"'{message}' not stored as symptoms", 
                    False,
                    f"CRITICAL: '{message}' was classified as symptoms! Intent: {intent}, Symptoms: {current_symptoms}"
                )
                all_passed = False
            else:
                expected_intent = "request_custom_date"
                passed = intent == expected_intent
                self.log_test(
                    f"'{message}' correctly handled", 
                    passed,
                    f"Intent: {intent} (Expected: {expected_intent})"
                )
                if not passed:
                    all_passed = False
        
        return all_passed
    
    async def test_symptom_update_guards(self):
        """Test 4: Guards prevent non-symptom data from being stored as symptoms"""
        print("🧪 Test 4: Symptom Update Guards")
        print("-" * 40)
        
        # Test messages that should NOT update symptoms
        non_symptom_messages = [
            ("3", "select_slot"),
            ("Other", "request_custom_date"), 
            ("Tomorrow 3pm", "request_custom_date"),
            ("4", "select_slot"),
            ("Different time", "request_custom_date")
        ]
        
        all_passed = True
        
        for message, expected_intent in non_symptom_messages:
            analysis = await analyze_message(message, current_step="current_symptoms", is_onboarding_complete=True)
            
            intent = analysis.get("intent")
            current_symptoms = analysis.get("entities", {}).get("current_symptoms")
            
            # These should NOT have current_symptoms entity filled
            should_not_have_symptoms = current_symptoms is None or current_symptoms.strip() == ""
            correct_intent = intent == expected_intent
            
            passed = should_not_have_symptoms and correct_intent
            
            self.log_test(
                f"Guard test: '{message}'",
                passed,
                f"Intent: {intent}, Symptoms entity: {current_symptoms}, Expected intent: {expected_intent}"
            )
            
            if not passed:
                all_passed = False
        
        # Test messages that SHOULD update symptoms
        symptom_messages = [
            ("Headache and fever", "provide_current_symptoms"),
            ("Back pain", "provide_current_symptoms"),
            ("Feeling dizzy today", "provide_current_symptoms")
        ]
        
        for message, expected_intent in symptom_messages:
            analysis = await analyze_message(message, current_step="current_symptoms", is_onboarding_complete=True)
            
            intent = analysis.get("intent") 
            current_symptoms = analysis.get("entities", {}).get("current_symptoms")
            
            # These SHOULD have symptoms
            has_symptoms = current_symptoms is not None and current_symptoms.strip() != ""
            correct_intent = intent == expected_intent
            
            passed = has_symptoms and correct_intent
            
            self.log_test(
                f"Symptom test: '{message}'",
                passed,
                f"Intent: {intent}, Symptoms: {current_symptoms}"
            )
            
            if not passed:
                all_passed = False
        
        return all_passed
    
    async def test_keep_current_value_handling(self):
        """Test 5: Keep current value intent handling"""
        print("🧪 Test 5: Keep Current Value Handling")
        print("-" * 40)
        
        keep_messages = [
            "keep",
            "Keep",
            "KEEP",
            "maintain",
            "same",
            "don't change"
        ]
        
        all_passed = True
        
        for message in keep_messages:
            analysis = await analyze_message(message, current_step="update_email", is_onboarding_complete=True)
            
            intent = analysis.get("intent")
            expected_intent = "keep_current_value"
            
            passed = intent == expected_intent
            
            self.log_test(
                f"Keep handling: '{message}'",
                passed,
                f"Intent: {intent} (Expected: {expected_intent})"
            )
            
            if not passed:
                all_passed = False
        
        return all_passed
    
    async def test_edge_case_scenarios(self):
        """Test 6: Edge cases that previously caused infinite loops"""
        print("🧪 Test 6: Edge Case Scenarios")
        print("-" * 40)
        
        edge_cases = [
            {
                "message": "",  # Empty message
                "context": "current_symptoms", 
                "description": "Empty message handling"
            },
            {
                "message": "   ",  # Whitespace only
                "context": "current_symptoms",
                "description": "Whitespace-only message" 
            },
            {
                "message": "123456",  # Invalid large number
                "context": "current_symptoms",
                "description": "Invalid large number"
            },
            {
                "message": "!@#$%",  # Special characters
                "context": "current_symptoms", 
                "description": "Special characters"
            }
        ]
        
        all_passed = True
        
        for case in edge_cases:
            try:
                analysis = await analyze_message(
                    case["message"],
                    current_step=case["context"],
                    is_onboarding_complete=True
                )
                
                # Should always return valid structure
                has_valid_structure = (
                    'intent' in analysis and 
                    'entities' in analysis and
                    isinstance(analysis['entities'], dict)
                )
                
                self.log_test(
                    case["description"],
                    has_valid_structure,
                    f"Intent: {analysis.get('intent')}, Structure valid: {has_valid_structure}"
                )
                
                if not has_valid_structure:
                    all_passed = False
                    
            except Exception as e:
                self.log_test(
                    case["description"],
                    False,
                    f"Exception: {str(e)}"
                )
                all_passed = False
        
        return all_passed
    
    async def run_all_tests(self):
        """Run all critical fix tests"""
        print("🚀 Critical Fixes Validation Test Suite")
        print("=" * 50)
        
        # Setup
        setup_ok = await self.setup_test_patient()
        if not setup_ok:
            print("❌ Failed to setup test patient")
            return False
        
        print()
        
        # Run tests
        test_results = []
        
        test_results.append(await self.test_gemini_json_parsing_stability())
        test_results.append(await self.test_context_aware_intent_detection()) 
        test_results.append(await self.test_other_as_custom_date_not_symptoms())
        test_results.append(await self.test_symptom_update_guards())
        test_results.append(await self.test_keep_current_value_handling())
        test_results.append(await self.test_edge_case_scenarios())
        
        # Summary
        print("📊 Test Results Summary")
        print("=" * 50)
        
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        
        individual_test_count = len(self.test_results)
        individual_passed = sum(1 for t in self.test_results if t["passed"])
        
        print(f"🏆 Test Suites: {passed_tests}/{total_tests} passed")
        print(f"🔍 Individual Tests: {individual_passed}/{individual_test_count} passed")
        
        all_passed = all(test_results)
        
        if all_passed:
            print("\n🎉 ALL CRITICAL FIXES VALIDATED!")
            print("✅ Gemini 2.5 Flash JSON parsing is stable")
            print("✅ Context-aware intent detection works")
            print("✅ 'Other' is handled as custom date, not symptoms")
            print("✅ Symptom update guards prevent data corruption")
            print("✅ Keep current value handling works")
            print("✅ Edge cases are handled gracefully")
            print("\n🛡️  The system is now protected against the previous failures!")
        else:
            print("\n❌ SOME TESTS FAILED")
            print("Failed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  ❌ {result['test']}: {result['details']}")
        
        return all_passed

async def main():
    """Main test function"""
    tester = CriticalFixesTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    asyncio.run(main()) 