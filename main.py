# backend/main.py
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from services.gemini_service import analyze_message, generate_dermatology_response
from services.supabase_service import (
    find_or_create_patient, book_slot, update_patient_email, 
    update_patient_onboarding_step, update_profile_field,
    complete_profile_update, find_or_create_availability_slot,
    get_upcoming_appointments, cancel_appointment, get_patient_onboarding_status
)
from services.gcal_service import create_calendar_event
from services.twilio_service import send_whatsapp_message
import json
import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import dateparser
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dr. Sunil Mishra's Derm & Hair AI Assistant", version="2.3.0")

# Helper functions for multi-step booking
async def store_booking_context(patient_id: str, context: dict):
    """Stores temporary booking choices (like month, date) for a patient."""
    await update_profile_field(patient_id, 'notes', json.dumps(context))

async def get_booking_context(patient: dict) -> dict:
    """Retrieves temporary booking choices for a patient."""
    if patient.get('notes'):
        try:
            return json.loads(patient['notes'])
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

async def send_status_updates(phone_number: str, stop_event: asyncio.Event):
    """Sends a timed, sequential series of status updates."""
    # Define the sequence of messages and the delay after each one
    status_messages = [
        ("Searching...", 1.5),
        ("Retrieving...", 2.0),
        ("Thinking...", 2.5),
        ("Analysing...", 2.0)
    ]
    
    for message, delay in status_messages:
        # Before sending the next message, check if the main task has already finished
        if stop_event.is_set():
            logger.info("Main task finished early. Halting status updates.")
            break
        
        try:
            # Send the status update
            await send_whatsapp_message(phone_number, message)
            # Wait for the specified delay, but allow the stop_event to interrupt the wait
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
            # If the wait is interrupted, it means the main task finished.
            break
        except asyncio.TimeoutError:
            # This is the expected behavior, meaning we waited the full delay.
            # Continue to the next message in the sequence.
            continue
            
    logger.info("Stopping the status update sequence.")

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Dr. Sunil Mishra's Derm & Hair AI Assistant is running"}

@app.post("/whatsapp-webhook")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    """
    Simplified and robust webhook for Dr. Sunil Mishra's Hair & Trichology Clinic
    """
    logger.info(f"Received message from {From}: {Body}")
    
    response = MessagingResponse()
    try:
        phone_number = From.replace("whatsapp:", "")
        patient = await find_or_create_patient(phone_number)
        
        if not patient:
            response.message("Sorry, I'm having system difficulties. Please try again later.")
            return Response(content=str(response), media_type="application/xml")

        onboarding_status = await get_patient_onboarding_status(patient['id'])
        current_step = onboarding_status.get('onboarding_step', 'start') if onboarding_status else 'start'
        onboarding_completed = patient.get('onboarding_completed', False)

        # --- 1. GATED ONBOARDING FLOW FOR NEW USERS ---
        if not onboarding_completed:
            logger.info(f"User {patient['id']} is in onboarding step: {current_step}")
            
            if current_step == 'start':
                response.message("Welcome to Dr. Sunil Mishra's Clinic! To create your patient profile, let's start with your full name.")
                await update_patient_onboarding_step(patient['id'], 'awaiting_name')
            
            elif current_step == 'awaiting_name':
                full_name = Body.strip()
                if len(full_name.split()) < 2 or not all(part.isalpha() for part in full_name.replace(" ", "")):
                    response.message("Please enter a valid full name (e.g., 'John Doe').")
                else:
                    await update_profile_field(patient['id'], 'full_name', full_name)
                    response.message(f"Thanks, {full_name.split()[0]}! How old are you?")
                    await update_patient_onboarding_step(patient['id'], 'awaiting_age')

            elif current_step == 'awaiting_age':
                age_str = Body.strip()
                if age_str.isdigit() and 1 <= int(age_str) <= 120:
                    await update_profile_field(patient['id'], 'age', int(age_str))
                    response.message("Great. What is your sex? (e.g., Male, Female, Other)")
                    await update_patient_onboarding_step(patient['id'], 'awaiting_sex')
                else:
                    response.message("Please enter a valid age as a number (e.g., '35').")

            elif current_step == 'awaiting_sex':
                sex = Body.strip().lower()
                if sex in ['male', 'female', 'other']:
                    await update_profile_field(patient['id'], 'gender', sex.capitalize())
                    response.message("Almost done! What is your email address? We'll use this for booking confirmations.")
                    await update_patient_onboarding_step(patient['id'], 'awaiting_email')
                else:
                    response.message("Please enter a valid option: Male, Female, or Other.")

            elif current_step == 'awaiting_email':
                email = Body.strip()
                if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    await update_patient_email(patient['id'], email)
                    await complete_profile_update(patient['id']) # This marks onboarding as done
                    response.message("Thank you! Your profile is complete. How can I help you today?\n\n- Ask any hair health questions (e.g., 'how do I reduce swelling after hair transplant?')\n- Type 'book appointment' to schedule.")
                else:
                    response.message("That doesn't look like a valid email. Please try again.")
            
            return Response(content=str(response), media_type="application/xml")

        # --- 2. EXISTING USER CONVERSATIONAL ROUTER ---
        analysis = await analyze_message(Body, current_step=current_step)
        intent = analysis.get("intent", "unknown").lower()
        logger.info(f"Patient Step: '{current_step}', Intent: '{intent}'")

        if intent == 'greeting' and current_step not in ['start', 'completed']:
            await update_patient_onboarding_step(patient['id'], 'start')
            await store_booking_context(patient['id'], {}) # Clear context
            response.message("It looks like you were in the middle of a conversation. Let's start over. How can I help you today?")

        # --- 1. HANDLE MULTI-STEP CONVERSATIONS (BOOKING, CANCELLING, RESCHEDULING) ---
        elif current_step.startswith('awaiting_'):
            
            # --- CANCELLATION CHOICE ---
            if current_step == 'awaiting_cancellation_choice':
                context = await get_booking_context(patient)
                appointments_to_cancel = context.get("appointments", [])
                try:
                    choice = int(Body.strip())
                    if 1 <= choice <= len(appointments_to_cancel):
                        appointment_to_cancel = appointments_to_cancel[choice - 1]
                        success = await cancel_appointment(appointment_to_cancel['id'], appointment_to_cancel['availability_id'])
                        if success:
                            response.message("Your appointment has been successfully cancelled.")
                        else:
                            response.message("Sorry, there was an error cancelling your appointment.")
                        await update_patient_onboarding_step(patient['id'], 'start')
                        await store_booking_context(patient['id'], {})
                    else:
                        response.message("That's not a valid number. Please choose from the list above.")
                except (ValueError, IndexError):
                    response.message("Please reply with just the number of the appointment to cancel.")

            # --- RESCHEDULING CHOICE ---
            elif current_step == 'awaiting_reschedule_choice':
                context = await get_booking_context(patient)
                appointments_to_reschedule = context.get("appointments", [])
                try:
                    choice = int(Body.strip())
                    if 1 <= choice <= len(appointments_to_reschedule):
                        appointment_to_reschedule = appointments_to_reschedule[choice - 1]
                        await cancel_appointment(appointment_to_reschedule['id'], appointment_to_reschedule['availability_id'])
                        
                        # Now, start the booking flow
                        today = datetime.now()
                        months, msg = [], "Your old appointment is cancelled. Let's find a new time. Please choose a month:\n\n"
                        for i in range(3):
                            dt = today + timedelta(days=31 * i)
                            months.append((dt.strftime('%B'), dt.year, dt.month))
                            msg += f"{i+1}️⃣ {months[i][0]} {months[i][1]}\n"
                        response.message(msg)
                        await update_patient_onboarding_step(patient['id'], 'awaiting_month_selection')
                        await store_booking_context(patient['id'], {"month_options": months})
                    else:
                        response.message("That's not a valid number. Please choose from the list above.")
                except (ValueError, IndexError):
                    response.message("Please reply with just the number of the appointment to reschedule.")
            
            # --- BOOKING FLOW ---
            else:
                # This logic is for the booking flow and remains the same
                if current_step == 'awaiting_month_selection':
                    context = await get_booking_context(patient)
                    month_options = context.get("month_options", [])
                    try:
                        choice = int(Body.strip())
                        if 1 <= choice <= len(month_options):
                            name, year, month_num = month_options[choice - 1]
                            await store_booking_context(patient['id'], {"year": year, "month": month_num, "month_name": name})
                            response.message(f"Great, you've selected {name}. Now, please enter the date (e.g., for the 15th, just type '15').")
                            await update_patient_onboarding_step(patient['id'], 'awaiting_date_selection')
                        else:
                            response.message("Please select a valid number from the list of months.")
                    except (ValueError, IndexError):
                        response.message("Please reply with just the number for your chosen month (e.g., '1').")

                elif current_step == 'awaiting_date_selection':
                    context = await get_booking_context(patient)
                    try:
                        day = int(Body.strip())
                        if not 1 <= day <= 31: raise ValueError("Invalid day")
                        context['day'] = day
                        await store_booking_context(patient['id'], context)
                        response.message("Perfect. Please enter your preferred time (e.g., '4 pm', '15:30'). Our hours are 10 AM to 10 PM.")
                        await update_patient_onboarding_step(patient['id'], 'awaiting_time_selection')
                    except ValueError:
                        response.message("Please reply with a valid date number (e.g., '15').")

                elif current_step == 'awaiting_time_selection':
                    context = await get_booking_context(patient)
                    parsed_time = dateparser.parse(Body.strip())
                    if not parsed_time:
                        response.message("I didn't understand that time. Please try again (e.g., '3pm', '14:00').")
                    else:
                        year, month, day = context['year'], context['month'], context['day']
                        local_tz = ZoneInfo("Asia/Kolkata")
                        start_time_local = datetime(year, month, day, parsed_time.hour, parsed_time.minute, 0, tzinfo=local_tz)
                        if not (10 <= start_time_local.hour < 22):
                            response.message("Our clinic hours are from 10 AM to 10 PM. Please choose a time within this range.")
                        elif start_time_local < datetime.now(local_tz):
                            response.message("That time is in the past. Please choose a future time.")
                        else:
                            end_time_utc = (start_time_local + timedelta(minutes=30)).astimezone(ZoneInfo("UTC"))
                            start_time_utc = start_time_local.astimezone(ZoneInfo("UTC"))
                            available_slot = await find_or_create_availability_slot(start_time_utc, end_time_utc)
                            if available_slot:
                                appointment = await book_slot(available_slot['id'], patient['id'])
                                if appointment:
                                    await store_booking_context(patient['id'], {})
                                    await update_patient_onboarding_step(patient['id'], 'start')
                                    calendar_event = await create_calendar_event(
                                        summary=f"Consultation: {patient.get('full_name', 'Patient')} with Dr. Sunil Mishra",
                                        start_time=available_slot['slot_start_time'],
                                        end_time=available_slot['slot_end_time'],
                                        attendee_email=patient.get('email'),
                                        location="Dr. Sunil Mishra's Hair & Trichology Clinic"
                                    )
                                    formatted_dt = start_time_local.strftime("%A, %B %d, %Y at %I:%M %p %Z")
                                    confirmation_msg = f"✅ Confirmed!\n\nYour consultation with Dr. Sunil Mishra is scheduled for:\n**{formatted_dt}**"
                                    if calendar_event and calendar_event.get("status") == "success":
                                        google_link = calendar_event.get("calendar_links", {}).get("google")
                                        if google_link:
                                            confirmation_msg += f"\n\n📅 *Add to Calendar:*\n{google_link}"
                                    response.message(confirmation_msg)
                                else:
                                    response.message("Sorry, that time was just booked. Please try another time.")
                            else:
                                response.message(f"Sorry, the {start_time_local.strftime('%I:%M %p')} slot is already taken. Please choose another time.")

        # --- 2. HANDLE TOP-LEVEL USER REQUESTS ---
        elif intent == 'request_booking':
            today = datetime.now()
            months, msg = [], "Of course! Let's schedule a consultation. Please choose a month:\n\n"
            for i in range(3):
                dt = today + timedelta(days=31 * i)
                months.append((dt.strftime('%B'), dt.year, dt.month))
                msg += f"{i+1}️⃣ {months[i][0]} {months[i][1]}\n"
            response.message(msg)
            await update_patient_onboarding_step(patient['id'], 'awaiting_month_selection')
            await store_booking_context(patient['id'], {"month_options": months})

        elif intent == 'request_cancellation':
            upcoming_appointments = await get_upcoming_appointments(patient['id'])
            if not upcoming_appointments:
                response.message("You have no upcoming appointments to cancel.")
            else:
                msg = "You have the following appointments. Which one would you like to cancel?\n\n"
                for i, appt in enumerate(upcoming_appointments):
                    appt_time = datetime.fromisoformat(appt['appointment_time'].replace('Z', '+00:00')).astimezone(ZoneInfo("Asia/Kolkata"))
                    msg += f"{i+1}️⃣ {appt_time.strftime('%A, %B %d at %I:%M %p')}\n"
                response.message(msg)
                await store_booking_context(patient['id'], {"appointments": upcoming_appointments})
                await update_patient_onboarding_step(patient['id'], 'awaiting_cancellation_choice')

        elif intent == 'request_reschedule':
            upcoming_appointments = await get_upcoming_appointments(patient['id'])
            if not upcoming_appointments:
                response.message("You have no upcoming appointments to reschedule. Would you like to book a new one?")
            else:
                msg = "You have the following appointments. Which one would you like to reschedule?\n\n"
                for i, appt in enumerate(upcoming_appointments):
                    appt_time = datetime.fromisoformat(appt['appointment_time'].replace('Z', '+00:00')).astimezone(ZoneInfo("Asia/Kolkata"))
                    msg += f"{i+1}️⃣ {appt_time.strftime('%A, %B %d at %I:%M %p')}\n"
                response.message(msg)
                await store_booking_context(patient['id'], {"appointments": upcoming_appointments})
                await update_patient_onboarding_step(patient['id'], 'awaiting_reschedule_choice')

        elif intent == 'dermatology_query':
            # --- START: DYNAMIC FEEDBACK FLOW ---
            
            # 1. Create a signal to stop the background task.
            stop_loop_event = asyncio.Event()
            
            # 2. Start the new background task that sends sequential status updates.
            status_task = asyncio.create_task(send_status_updates(phone_number, stop_loop_event))
            
            # 3. Run the time-consuming AI call.
            logger.info("[main] Calling generate_dermatology_response...")
            dermatology_response = await generate_dermatology_response(Body)
            logger.info(f"[main] Received response from Docser API: '{dermatology_response[:100] if dermatology_response else 'None'}...'")
            
            # 4. Signal the background task to stop.
            stop_loop_event.set()
            await status_task # Wait for the status loop to finish its current iteration and exit.
            
            # 5. Deliver the final response, including "Drafting...".
            await send_whatsapp_message(phone_number, "Drafting...")
            await asyncio.sleep(1.5) # Quick pause for realism.
            
            if dermatology_response:
                await send_whatsapp_message(phone_number, dermatology_response)
            else:
                await send_whatsapp_message(phone_number, "I'm sorry, I couldn't process that question right now.")
            
            return Response(content=str(MessagingResponse()), media_type="application/xml")
            # --- END: DYNAMIC FEEDBACK FLOW ---
        
        elif intent == 'greeting':
            response.message(f"Hello, {patient.get('full_name', '').split()[0]}! How can I help? You can ask a question or type 'book appointment'.")
        
        else: # Unknown intents
            response.message("I'm sorry, I didn't understand that. You can ask a hair health question, or type 'book appointment'.")

        final_response_str = str(response)
        logger.info(f"Final TwiML response being sent to Twilio:\n{final_response_str}")
        return Response(content=final_response_str, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"FATAL Error in webhook: {e}", exc_info=True)
        response = MessagingResponse()
        response.message("I'm sorry, a system error occurred. Please try again in a few moments.")
        return Response(content=str(response), media_type="application/xml")

@app.get("/status")
async def get_status():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Doctor AI WhatsApp Assistant",
        "timestamp": datetime.now().isoformat()
    }