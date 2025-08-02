import os
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from services.gemini_service import analyze_message
from services.supabase_service import (
    find_or_create_patient, get_available_slots, book_slot, create_appointment, 
    update_patient_email, update_patient_onboarding_step, update_patient_age,
    update_patient_gender, update_patient_blood_group, update_patient_symptoms,
    update_patient_allergies, create_appointment_request, get_patient_onboarding_status
)
from services.gcal_service import create_calendar_event
from services.twilio_service import send_whatsapp_message
import json
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Doctor AI WhatsApp Assistant", version="1.0.0")

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Doctor AI WhatsApp Assistant is running"}

@app.post("/whatsapp-webhook")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    """
    Main webhook endpoint that handles incoming WhatsApp messages
    """
    logger.info(f"Received message from {From}: {Body}")
    
    try:
        # Extract phone number (remove whatsapp: prefix)
        phone_number = From.replace("whatsapp:", "")
        
        # Find or create patient
        patient = await find_or_create_patient(phone_number)
        logger.info(f"Patient: {patient}")
        
        # Analyze message intent using Gemini
        analysis = await analyze_message(Body)
        logger.info(f"Analysis: {analysis}")
        
        intent = analysis.get("intent", "").lower()
        entities = analysis.get("entities", {})
        
        response = MessagingResponse()
        
        # Handle different intents
        if intent == "request_booking" or intent == "book_appointment":
            # User wants to book an appointment - first check if they have email
            if not patient.get('email'):
                email_request_msg = "I'd be happy to help you book an appointment! 📅\n\n"
                email_request_msg += "To send you a calendar invite, I'll need your email address.\n\n"
                email_request_msg += "Please reply with your email address (e.g., john@example.com)"
                response.message(email_request_msg)
            else:
                # Patient has email, show available slots
                available_slots = await get_available_slots()
                
                if available_slots:
                    slots_text = "Here are the available appointment slots:\n\n"
                    for i, slot in enumerate(available_slots[:5], 1):  # Show max 5 slots
                        start_time = slot['slot_start_time']
                        # Parse and format the datetime
                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                        slots_text += f"{i}. {formatted_time}\n"
                    
                    slots_text += "\nReply with the number of your preferred slot (e.g., '1' for the first slot)."
                    response.message(slots_text)
                else:
                    response.message("I'm sorry, there are no available appointment slots at the moment. Please try again later or contact the clinic directly.")
        
        elif intent == "provide_email":
            # User is providing their email address
            email = entities.get("email")
            if email:
                # Update patient with email
                updated_patient = await update_patient_email(patient['id'], email)
                if updated_patient:
                    # Show available slots after email is saved
                    available_slots = await get_available_slots()
                    
                    if available_slots:
                        confirmation_msg = f"✅ Thank you! I've saved your email: {email}\n\n"
                        confirmation_msg += "Here are the available appointment slots:\n\n"
                        
                        for i, slot in enumerate(available_slots[:5], 1):  # Show max 5 slots
                            start_time = slot['slot_start_time']
                            # Parse and format the datetime
                            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                            confirmation_msg += f"{i}. {formatted_time}\n"
                        
                        confirmation_msg += "\nReply with the number of your preferred slot (e.g., '1' for the first slot)."
                        response.message(confirmation_msg)
                    else:
                        response.message(f"✅ Thank you! I've saved your email: {email}\n\nUnfortunately, there are no available appointment slots at the moment. Please try again later.")
                else:
                    response.message("Sorry, there was an error saving your email. Please try again.")
            else:
                response.message("I didn't recognize that as a valid email address. Please reply with your email in the format: name@example.com")
        
        elif intent == "confirm_slot" or intent == "select_slot":
            # User is confirming a slot selection
            slot_number = entities.get("slot_number")
            if not slot_number:
                # Try to extract number from message
                try:
                    slot_number = int(Body.strip())
                except ValueError:
                    response.message("Please reply with the number of your preferred slot (e.g., '1', '2', etc.)")
                    return Response(content=str(response), media_type="application/xml")
            else:
                # Convert string slot_number from Gemini to integer
                try:
                    slot_number = int(slot_number)
                except (ValueError, TypeError):
                    response.message("Please reply with the number of your preferred slot (e.g., '1', '2', etc.)")
                    return Response(content=str(response), media_type="application/xml")
            
            # Check if patient has email
            if not patient.get('email'):
                response.message("I need your email address first to send you a calendar invite. Please provide your email address (e.g., john@example.com)")
                return Response(content=str(response), media_type="application/xml")
            
            available_slots = await get_available_slots()
            
            if 1 <= slot_number <= len(available_slots):
                selected_slot = available_slots[slot_number - 1]
                
                # Book the slot
                appointment = await book_slot(selected_slot['id'], patient['id'])
                
                if appointment:
                    # Create Google Calendar event with patient's email
                    calendar_event = await create_calendar_event(
                        summary=f"Appointment with {patient.get('full_name', 'Patient')}",
                        start_time=selected_slot['slot_start_time'],
                        end_time=selected_slot['slot_end_time'],
                        attendee_email=patient.get('email')  # Now we have the email!
                    )
                    
                    # Format confirmation message
                    start_time = selected_slot['slot_start_time']
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                    
                    confirmation_msg = f"✅ Your appointment is confirmed!\n\n"
                    confirmation_msg += f"📅 Date & Time: {formatted_time}\n"
                    confirmation_msg += f"👨‍⚕️ Doctor: Dr. Sunil Mishra\n"
                    confirmation_msg += f"📧 Email: {patient.get('email')}\n"
                    confirmation_msg += f"📞 Phone: {phone_number}\n\n"
                    
                    if calendar_event and calendar_event.get('status') == 'success':
                        confirmation_msg += f"📅 Calendar invite sent to {patient.get('email')}\n\n"
                    elif calendar_event and calendar_event.get('status') == 'skipped':
                        confirmation_msg += f"📅 Calendar: Not configured (appointment still confirmed)\n\n"
                    
                    confirmation_msg += f"Please arrive 15 minutes early. If you need to reschedule, please contact us at least 24 hours in advance."
                    
                    response.message(confirmation_msg)
                else:
                    response.message("Sorry, there was an error booking your appointment. Please try again.")
            else:
                response.message("Invalid slot number. Please choose a number from the available slots.")
        
        elif intent == "chitchat" or intent == "greeting":
            # Handle greetings and general questions
            greeting_msg = "Hello! I'm Dr. Sunil Mishra's AI assistant. I can help you book an appointment. "
            greeting_msg += "Just say 'I want to book an appointment' or 'book appointment' to get started."
            response.message(greeting_msg)
        
        else:
            # Default response for unrecognized intents
            help_msg = "I can help you book an appointment with Dr. Sunil Mishra. "
            help_msg += "Just say 'book appointment' to see available slots, or reply with a slot number to confirm your booking."
            response.message(help_msg)
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        response = MessagingResponse()
        response.message("Sorry, I encountered an error. Please try again later.")
        return Response(content=str(response), media_type="application/xml")

@app.get("/status")
async def get_status():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Doctor AI WhatsApp Assistant",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 