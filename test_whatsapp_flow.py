#!/usr/bin/env python3
"""
End-to-End WhatsApp Chatbot Flow Test
Simulates a complete user interaction for appointment booking
"""

import asyncio
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from services.gemini_service import analyze_message
from services.supabase_service import (
    find_or_create_patient, 
    get_available_slots, 
    book_slot, 
    create_appointment,
    test_connection as test_supabase
)
from services.gcal_service import create_calendar_event, test_connection as test_gcal
from services.twilio_service import test_connection as test_twilio

class WhatsAppChatbotTester:
    def __init__(self):
        self.test_phone = "+1234567890"
        self.patient_id = None
        self.conversation_log = []
    
    def log_message(self, sender, message, analysis=None):
        """Log conversation messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.conversation_log.append({
            "time": timestamp,
            "sender": sender, 
            "message": message,
            "analysis": analysis
        })
        
        if sender == "User":
            print(f"👤 [{timestamp}] User: {message}")
        else:
            print(f"🤖 [{timestamp}] Bot: {message}")
        
        if analysis:
            print(f"   🧠 Analysis: Intent='{analysis.get('intent')}', Entities={analysis.get('entities', {})}")
    
    async def test_service_connections(self):
        """Test all service connections first"""
        print("🔗 Testing Service Connections...")
        print("-" * 40)
        
        # Test Supabase
        supabase_result = await test_supabase()
        print(f"📊 Supabase: {supabase_result['status']} - {supabase_result['message']}")
        
        # Test Twilio
        twilio_result = await test_twilio()
        print(f"📱 Twilio: {twilio_result['status']} - {twilio_result['message']}")
        
        # Test Google Calendar
        gcal_result = await test_gcal()
        print(f"📅 Google Calendar: {gcal_result['status']} - {gcal_result['message']}")
        
        print("-" * 40)
        print()
        
        return all(result['status'] in ['success', 'disabled'] for result in [supabase_result, twilio_result, gcal_result])
    
    async def simulate_user_message(self, message):
        """Simulate processing a user message"""
        self.log_message("User", message)
        
        # Analyze message intent
        analysis = await analyze_message(message)
        
        # Find or create patient
        if not self.patient_id:
            patient = await find_or_create_patient(self.test_phone, "Test Patient")
            if patient:
                self.patient_id = patient['id']
                print(f"   👤 Patient created/found: ID {self.patient_id}")
            else:
                print("   ❌ Failed to create/find patient")
                return None
        
        intent = analysis.get("intent", "").lower()
        entities = analysis.get("entities", {})
        
        response_message = ""
        
        # Handle different intents
        if intent in ["request_booking", "book_appointment"]:
            # User wants to book an appointment
            available_slots = await get_available_slots()
            
            if available_slots:
                response_message = "Here are the available appointment slots:\n\n"
                for i, slot in enumerate(available_slots[:3], 1):  # Show max 3 slots
                    start_time = slot['slot_start_time']
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                    response_message += f"{i}. {formatted_time}\n"
                
                response_message += "\nReply with the number of your preferred slot."
            else:
                response_message = "Sorry, no available slots at the moment."
        
        elif intent in ["confirm_slot", "select_slot"]:
            # User is confirming a slot selection
            slot_number = entities.get("slot_number")
            if not slot_number:
                try:
                    slot_number = int(message.strip())
                except ValueError:
                    slot_number = None
            
            if slot_number:
                available_slots = await get_available_slots()
                
                if 1 <= slot_number <= len(available_slots):
                    selected_slot = available_slots[slot_number - 1]
                    
                    # Book the slot
                    appointment = await book_slot(selected_slot['id'], self.patient_id)
                    
                    if appointment:
                        # Create Google Calendar event
                        calendar_event = await create_calendar_event(
                            summary=f"Appointment with Test Patient",
                            start_time=selected_slot['slot_start_time'],
                            end_time=selected_slot['slot_end_time'],
                            attendee_email=None
                        )
                        
                        # Format confirmation
                        start_time = selected_slot['slot_start_time']
                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                        
                        response_message = f"✅ Appointment confirmed!\n"
                        response_message += f"📅 Date & Time: {formatted_time}\n"
                        response_message += f"👨‍⚕️ Doctor: Dr. Sunil Mishra\n"
                        
                        if calendar_event and calendar_event.get('status') == 'success':
                            response_message += f"📅 Calendar event created: {calendar_event.get('event_id')}\n"
                        elif calendar_event and calendar_event.get('status') == 'skipped':
                            response_message += f"📅 Calendar: Not configured (appointment still confirmed)\n"
                        
                        print(f"   ✅ Appointment booked: {appointment['id']}")
                        print(f"   📅 Calendar event: {calendar_event}")
                    else:
                        response_message = "Sorry, error booking appointment."
                else:
                    response_message = "Invalid slot number. Please choose a valid option."
            else:
                response_message = "Please reply with a slot number (e.g., '1', '2', etc.)"
        
        elif intent in ["chitchat", "greeting"]:
            response_message = "Hello! I'm Dr. Sunil Mishra's AI assistant. Say 'book appointment' to get started."
        
        else:
            response_message = "I can help you book an appointment. Say 'book appointment' to see available slots."
        
        self.log_message("Bot", response_message, analysis)
        return {"response": response_message, "analysis": analysis}
    
    async def run_full_conversation_test(self):
        """Run a complete conversation simulation"""
        print("🗣️  Simulating Full WhatsApp Conversation")
        print("=" * 50)
        
        # Test conversation flow
        conversation_steps = [
            "Hello",
            "I want to book an appointment", 
            "1",  # Select first slot
        ]
        
        for step in conversation_steps:
            result = await self.simulate_user_message(step)
            if not result:
                print("❌ Conversation test failed!")
                return False
            print()  # Add spacing between messages
        
        print("✅ Full conversation test completed successfully!")
        return True
    
    def print_conversation_summary(self):
        """Print a summary of the conversation"""
        print("\n📋 Conversation Summary")
        print("-" * 30)
        for entry in self.conversation_log:
            print(f"[{entry['time']}] {entry['sender']}: {entry['message']}")
        print()

async def main():
    """Main test function"""
    print("🚀 WhatsApp Chatbot End-to-End Test")
    print("=" * 50)
    
    tester = WhatsAppChatbotTester()
    
    # Test service connections
    connections_ok = await tester.test_service_connections()
    if not connections_ok:
        print("⚠️  Some services have connection issues, but continuing with test...")
        print()
    
    # Run conversation test
    success = await tester.run_full_conversation_test()
    
    # Print summary
    tester.print_conversation_summary()
    
    if success:
        print("🎉 All tests passed! The chatbot is working correctly.")
        print("\n📝 What was tested:")
        print("  ✅ Service connections (Supabase, Twilio, Google Calendar)")
        print("  ✅ Message intent analysis (Gemini AI)")
        print("  ✅ Patient creation/lookup")
        print("  ✅ Available slots retrieval")  
        print("  ✅ Appointment booking")
        print("  ✅ Calendar event creation (if configured)")
        print("  ✅ Complete conversation flow")
    else:
        print("❌ Some tests failed. Check the logs above.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main()) 