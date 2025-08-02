from supabase import create_client, Client
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import uuid
import time
import asyncio

logger = logging.getLogger(__name__)

# Initialize Supabase client lazily
from dotenv import load_dotenv

supabase: Client = None

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # Base delay in seconds
MAX_DELAY = 8.0   # Maximum delay in seconds

def get_supabase_client():
    global supabase
    if supabase is None:
        load_dotenv()  # Load env vars here
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not found in environment variables")
            return None
        else:
            supabase = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
    return supabase

async def retry_with_backoff(func, *args, **kwargs):
    """
    Retry function with exponential backoff for network resilience.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                # Last attempt, re-raise the exception
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
    
    raise Exception("Max retries exceeded")

async def execute_with_retry(operation_func):
    """
    Execute Supabase operation with retry logic for connection issues.
    """
    return await retry_with_backoff(operation_func)

async def find_or_create_patient(phone_number: str, full_name: str = None) -> Dict[str, Any]:
    """
    Find existing patient by phone number or create a new one with retry logic.
    
    Args:
        phone_number: Patient's phone number
        full_name: Patient's full name (optional)
    
    Returns:
        Patient record dictionary
    """
    async def _find_or_create_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Try to find existing patient
        result = supabase_client.table('patients').select('*').eq('phone_number', phone_number).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Found existing patient: {phone_number}")
            return result.data[0]
        
        # Create new patient if not found
        patient_data = {
            'phone_number': phone_number,
            'full_name': full_name or f"Patient {phone_number[-4:]}",  # Use last 4 digits as default name
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase_client.table('patients').insert(patient_data).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Created new patient: {phone_number}")
            return result.data[0]
        else:
            logger.error(f"Failed to create patient: {result}")
            return None
    
    try:
        return await execute_with_retry(_find_or_create_operation)
    except Exception as e:
        logger.error(f"Error in find_or_create_patient after retries: {e}")
        return None

async def update_patient_email(patient_id: str, email: str) -> Dict[str, Any]:
    """
    Update patient's email address with retry logic.
    
    Args:
        patient_id: Patient's ID
        email: Patient's email address
    
    Returns:
        Updated patient record dictionary
    """
    async def _update_email_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Update patient email
        result = supabase_client.table('patients')\
            .update({'email': email, 'updated_at': datetime.now().isoformat()})\
            .eq('id', patient_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Updated patient email: {patient_id} -> {email}")
            return result.data[0]
        else:
            logger.error(f"Failed to update patient email: {result}")
            return None
    
    try:
        return await execute_with_retry(_update_email_operation)
    except Exception as e:
        logger.error(f"Error updating patient email after retries: {e}")
        return None

async def get_available_slots(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get available appointment slots with retry logic.
    
    Args:
        limit: Maximum number of slots to return
    
    Returns:
        List of available slot dictionaries
    """
    async def _get_slots_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return []
            
        # Get current time
        current_time = datetime.now().isoformat()
        
        # Query available slots
        result = supabase_client.table('doctor_availability')\
            .select('*')\
            .eq('is_booked', False)\
            .gte('slot_start_time', current_time)\
            .order('slot_start_time')\
            .limit(limit)\
            .execute()
        
        if result.data:
            logger.info(f"Found {len(result.data)} available slots")
            return result.data
        else:
            logger.warning("No available slots found")
            return []
    
    try:
        return await execute_with_retry(_get_slots_operation)
    except Exception as e:
        logger.error(f"Error getting available slots after retries: {e}")
        return []

async def book_slot(slot_id: str, patient_id: str) -> Dict[str, Any]:
    """
    Books an appointment slot by marking it as booked and creating an appointment record.
    This version is simplified to work with the logic in main.py.
    
    Args:
        slot_id: ID of the slot to book.
        patient_id: ID of the patient.
    
    Returns:
        The new appointment record dictionary or None if it failed.
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # First, atomically mark the slot as booked. 
        # The '.eq('is_booked', False)' ensures we don't double-book.
        slot_update = supabase_client.table('doctor_availability')\
            .update({'is_booked': True})\
            .eq('id', slot_id)\
            .eq('is_booked', False)\
            .execute()
        
        if not slot_update.data:
            logger.warning(f"Failed to book slot {slot_id} - it was likely booked by another user.")
            return None
        
        slot = slot_update.data[0]
        
        # Now, create the corresponding appointment record
        appointment_data = {
            'patient_id': patient_id,
            'availability_id': slot_id,
            'appointment_time': slot['slot_start_time'],
            'status': 'confirmed'
        }
        
        appointment_result = supabase_client.table('appointments').insert(appointment_data).execute()
        
        if appointment_result.data:
            logger.info(f"Successfully created appointment {appointment_result.data[0]['id']} for patient {patient_id}")
            return appointment_result.data[0]
        else:
            # If creating the appointment fails, we must un-book the slot to prevent it from being locked.
            logger.error("CRITICAL: Slot was booked but appointment record failed. Reverting slot booking.")
            supabase_client.table('doctor_availability').update({'is_booked': False}).eq('id', slot_id).execute()
            return None
            
    except Exception as e:
        logger.error(f"Error in book_slot transaction: {e}")
        return None

async def create_availability_slot(start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """
    Creates a new, single availability slot in the database.
    
    Args:
        start_time: The start time of the slot (datetime object).
        end_time: The end time of the slot (datetime object).
        
    Returns:
        The newly created slot dictionary or None if it fails.
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None

        slot_data = {
            'slot_start_time': start_time.isoformat(),
            'slot_end_time': end_time.isoformat(),
            'is_booked': False, # Important: Initially not booked
        }

        result = supabase_client.table('doctor_availability').insert(slot_data).execute()
        
        if result.data and len(result.data) > 0:
            new_slot = result.data[0]
            logger.info(f"Successfully created custom availability slot: {new_slot['id']}")
            return new_slot
        else:
            logger.error(f"Failed to create custom availability slot: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating custom availability slot: {e}")
        return None

async def find_or_create_availability_slot(start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
    """
    Finds an existing availability slot or creates a new one if none exists.
    This function is key to preventing double-bookings while allowing dynamic scheduling.
    
    Args:
        start_time: The start time of the slot (datetime object in UTC).
        end_time: The end time of the slot (datetime object in UTC).
        
    Returns:
        Available slot dictionary if successful, None if slot is already booked.
    """
    async def _find_or_create_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
        
        # First, check if a slot already exists for this exact time
        existing_result = supabase_client.table('doctor_availability')\
            .select('*')\
            .eq('slot_start_time', start_time.isoformat())\
            .execute()
        
        if existing_result.data and len(existing_result.data) > 0:
            existing_slot = existing_result.data[0]
            if existing_slot['is_booked']:
                logger.info(f"Slot at {start_time.isoformat()} is already booked")
                return None  # Slot exists but is already booked
            else:
                logger.info(f"Found available existing slot at {start_time.isoformat()}")
                return existing_slot  # Slot exists and is available
        
        # Check for any overlapping slots (conflict detection)
        overlap_result = supabase_client.table('doctor_availability')\
            .select('*')\
            .lt('slot_start_time', end_time.isoformat())\
            .gt('slot_end_time', start_time.isoformat())\
            .eq('is_booked', True)\
            .execute()
        
        if overlap_result.data and len(overlap_result.data) > 0:
            logger.info(f"Overlapping booked slot found, cannot create slot at {start_time.isoformat()}")
            return None  # There's a conflicting booked slot
        
        # No conflicts, create a new slot
        slot_data = {
            'slot_start_time': start_time.isoformat(),
            'slot_end_time': end_time.isoformat(),
            'is_booked': False
        }
        
        create_result = supabase_client.table('doctor_availability').insert(slot_data).execute()
        
        if create_result.data and len(create_result.data) > 0:
            new_slot = create_result.data[0]
            logger.info(f"Successfully created new availability slot: {new_slot['id']} at {start_time.isoformat()}")
            return new_slot
        else:
            logger.error(f"Failed to create availability slot: {create_result}")
            return None
    
    try:
        return await retry_with_backoff(_find_or_create_operation)
    except Exception as e:
        logger.error(f"Error in find_or_create_availability_slot: {e}")
        return None

async def get_upcoming_appointments(patient_id: str) -> List[Dict[str, Any]]:
    """
    Fetches all future, confirmed appointments for a patient.
    """
    async def _get_upcoming_operation():
        supabase_client = get_supabase_client()
        if not supabase_client: return []

        now_utc = datetime.now(ZoneInfo("UTC")).isoformat()
        
        result = supabase_client.table('appointments')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('status', 'confirmed')\
            .gte('appointment_time', now_utc)\
            .order('appointment_time', desc=False)\
            .execute()
            
        return result.data if result.data else []

    try:
        return await execute_with_retry(_get_upcoming_operation)
    except Exception as e:
        logger.error(f"Error fetching upcoming appointments: {e}")
        return []

async def find_upcoming_appointment(patient_id: str) -> Optional[Dict[str, Any]]:
    """
    Finds the next upcoming 'confirmed' appointment for a given patient.
    
    Args:
        patient_id: The UUID of the patient.
    
    Returns:
        A dictionary of the appointment details if found, otherwise None.
    """
    async def _find_operation():
        supabase_client = get_supabase_client()
        if not supabase_client: return None
        
        # Get the current time in UTC to compare against appointment times
        now_utc = datetime.now(ZoneInfo("UTC")).isoformat()
        
        # Query the appointments table
        result = supabase_client.table('appointments')\
            .select('*, doctor_availability(*)')\
            .eq('patient_id', patient_id)\
            .eq('status', 'confirmed')\
            .gte('appointment_time', now_utc)\
            .order('appointment_time', desc=False)\
            .limit(1)\
            .execute()
            
        if result.data:
            logger.info(f"Found upcoming appointment for patient {patient_id}: {result.data[0]['id']}")
            return result.data[0]
        else:
            logger.info(f"No upcoming appointments found for patient {patient_id}")
            return None
            
    try:
        return await retry_with_backoff(_find_operation)
    except Exception as e:
        logger.error(f"Error finding upcoming appointment: {e}")
        return None

async def cancel_appointment(appointment_id: str, availability_id: Optional[str] = None) -> bool:
    """
    Cancels an appointment and, if an availability_id is provided, frees the associated slot.
    This is the single, robust function for all cancellation needs.
    """
    async def _cancel_operation():
        supabase_client = get_supabase_client()
        if not supabase_client: return False
        
        # Step 1: Update the appointment status to 'cancelled'
        appt_update_res = supabase_client.table('appointments')\
            .update({'status': 'cancelled'})\
            .eq('id', appointment_id)\
            .execute()

        if not appt_update_res.data:
            logger.warning(f"Could not find or update appointment status for {appointment_id}.")
            return False # If we can't even find the appointment, it's a failure.
        
        # Step 2: If it was linked to a specific slot, free up that slot
        if availability_id:
            logger.info(f"Freeing up availability slot {availability_id} for cancelled appointment {appointment_id}.")
            slot_update_res = supabase_client.table('doctor_availability')\
                .update({'is_booked': False})\
                .eq('id', availability_id)\
                .execute()

            if not slot_update_res.data:
                 # This is a warning, not a critical failure, as the appointment itself was cancelled.
                 logger.warning(f"Could not free up availability slot {availability_id} after cancellation.")

        logger.info(f"Successfully processed cancellation for appointment {appointment_id}.")
        return True

    try:
        return await execute_with_retry(_cancel_operation)
    except Exception as e:
        logger.error(f"Error during cancel_appointment transaction: {e}")
        return False

async def get_available_dates_by_month(year: int, month: int) -> List[int]:
    """
    Finds all unique dates within a given month and year that have at least one available slot.
    
    Args:
        year: The year to check (e.g., 2025).
        month: The month to check (e.g., 8 for August).
        
    Returns:
        A sorted list of unique available dates (e.g., [1, 2, 5, 7]).
    """
    async def _get_dates_operation():
        supabase_client = get_supabase_client()
        if not supabase_client: return []

        # Define the start and end of the month in UTC
        start_of_month = datetime(year, month, 1, tzinfo=ZoneInfo("UTC"))
        # To get the end of the month, go to the next month and subtract one day
        next_month = start_of_month.replace(day=28) + timedelta(days=4) 
        end_of_month = next_month - timedelta(days=next_month.day)
        end_of_month = end_of_month.replace(hour=23, minute=59, second=59)

        # Query the database
        result = supabase_client.table('doctor_availability')\
            .select('slot_start_time')\
            .eq('is_booked', False)\
            .gte('slot_start_time', start_of_month.isoformat())\
            .lte('slot_start_time', end_of_month.isoformat())\
            .order('slot_start_time', desc=False)\
            .execute()

        if result.data:
            # Use a set to store unique dates to avoid duplicates
            available_dates = set()
            for slot in result.data:
                # Convert slot time from UTC string to a datetime object
                slot_time_utc = datetime.fromisoformat(slot['slot_start_time'].replace('Z', '+00:00'))
                # Add the day of the month to our set
                available_dates.add(slot_time_utc.day)
            
            # Return a sorted list of the unique dates
            return sorted(list(available_dates))
        return []

    try:
        return await retry_with_backoff(_get_dates_operation)
    except Exception as e:
        logger.error(f"Error getting available dates for {year}-{month}: {e}")
        return []

async def get_available_times_for_date(year: int, month: int, day: int) -> List[Dict[str, Any]]:
    """
    Finds all available time slots for a specific date.
    
    Args:
        year: The year of the date.
        month: The month of the date.
        day: The day of the date.
        
    Returns:
        A list of available slot dictionaries for that day.
    """
    async def _get_times_operation():
        supabase_client = get_supabase_client()
        if not supabase_client: return []

        # Define the start and end of the specified day in UTC
        start_of_day = datetime(year, month, day, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        end_of_day = datetime(year, month, day, 23, 59, 59, tzinfo=ZoneInfo("UTC"))
        
        # Query the database
        result = supabase_client.table('doctor_availability')\
            .select('*')\
            .eq('is_booked', False)\
            .gte('slot_start_time', start_of_day.isoformat())\
            .lte('slot_start_time', end_of_day.isoformat())\
            .order('slot_start_time', desc=False)\
            .execute()

        return result.data if result.data else []

    try:
        return await retry_with_backoff(_get_times_operation)
    except Exception as e:
        logger.error(f"Error getting available times for {year}-{month}-{day}: {e}")
        return []

async def create_appointment(patient_id: str, slot_id: str, appointment_time: str) -> Dict[str, Any]:
    """
    Create an appointment record.
    
    Args:
        patient_id: ID of the patient
        slot_id: ID of the availability slot
        appointment_time: Time of the appointment
    
    Returns:
        Appointment record dictionary
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        appointment_data = {
            'patient_id': patient_id,
            'availability_id': slot_id,
            'appointment_time': appointment_time,
            'status': 'confirmed',
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase_client.table('appointments').insert(appointment_data).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Created appointment: {result.data[0]['id']}")
            return result.data[0]
        else:
            logger.error(f"Failed to create appointment: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating appointment: {e}")
        return None

async def get_patient_appointments(patient_id: str) -> List[Dict[str, Any]]:
    """
    Get all appointments for a patient.
    
    Args:
        patient_id: ID of the patient
    
    Returns:
        List of appointment dictionaries
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return []
            
        result = supabase_client.table('appointments')\
            .select('*, doctor_availability(*)')\
            .eq('patient_id', patient_id)\
            .order('appointment_time')\
            .execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"Error getting patient appointments: {e}")
        return []

async def add_availability_slots(slots: List[Dict[str, Any]]) -> bool:
    """
    Add new availability slots (for admin use).
    
    Args:
        slots: List of slot dictionaries with start_time and end_time
    
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return False
            
        result = supabase_client.table('doctor_availability').insert(slots).execute()
        
        if result.data:
            logger.info(f"Added {len(result.data)} availability slots")
            return True
        else:
            logger.error("Failed to add availability slots")
            return False
            
    except Exception as e:
        logger.error(f"Error adding availability slots: {e}")
        return False

# Enhanced onboarding functions with current symptoms separation
async def update_patient_onboarding_step(patient_id: str, step: str) -> Dict[str, Any]:
    """
    Update patient's current onboarding step with retry logic.
    
    Args:
        patient_id: Patient's ID
        step: Current onboarding step
    
    Returns:
        Updated patient record dictionary
    """
    async def _update_step_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Update patient onboarding step
        result = supabase_client.table('patients')\
            .update({'onboarding_step': step, 'updated_at': datetime.now().isoformat()})\
            .eq('id', patient_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Updated patient onboarding step: {patient_id} -> {step}")
            return result.data[0]
        else:
            logger.error(f"Failed to update patient onboarding step: {result}")
            return None
    
    try:
        return await execute_with_retry(_update_step_operation)
    except Exception as e:
        logger.error(f"Error updating patient onboarding step after retries: {e}")
        return None

async def get_patient_profile_summary(patient_id: str) -> Dict[str, Any]:
    """
    Get patient's profile summary (demographics only, excluding current symptoms).
    
    Args:
        patient_id: Patient's ID
    
    Returns:
        Patient profile summary dictionary
    """
    async def _get_profile_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Get patient demographics
        result = supabase_client.table('patients')\
            .select('id, full_name, email, age, gender, onboarding_completed')\
            .eq('id', patient_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            logger.warning(f"Patient profile not found: {patient_id}")
            return None
    
    try:
        return await execute_with_retry(_get_profile_operation)
    except Exception as e:
        logger.error(f"Error getting patient profile after retries: {e}")
        return None

async def update_current_symptoms(patient_id: str, current_symptoms: str) -> Dict[str, Any]:
    """
    Update patient's current symptoms for this appointment (temporary, not stored in profile).
    This function is separate from profile updates to ensure symptoms are always fresh.
    
    Args:
        patient_id: Patient's ID
        current_symptoms: Current symptoms for this appointment
    
    Returns:
        Updated patient record dictionary with current symptoms
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Store current symptoms in a session-like manner
        # We'll use the existing symptoms field but mark it as current/temporary
        result = supabase_client.table('patients')\
            .update({
                'symptoms': current_symptoms,  # Temporary storage for current appointment
                'symptoms_timestamp': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Updated current symptoms for patient: {patient_id}")
            return result.data[0]
        else:
            logger.error(f"Failed to update current symptoms: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error updating current symptoms: {e}")
        return None

async def update_profile_field(patient_id: str, field_name: str, field_value: str) -> Dict[str, Any]:
    """
    Update a specific profile field (demographics only).
    
    Args:
        patient_id: Patient's ID
        field_name: Name of the field to update (email, age, gender)
        field_value: New value for the field
    
    Returns:
        Updated patient record dictionary
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
        
        # Allowed fields for profile updates
        # Added 'notes' to allow booking context storage
        allowed_fields = ['email', 'age', 'gender', 'full_name', 'notes']
        
        if field_name not in allowed_fields:
            logger.error(f"Field '{field_name}' not allowed for profile updates")
            return None
            
        # Prepare update data
        update_data = {
            field_name: field_value,
            'updated_at': datetime.now().isoformat()
        }
        

        
        # Special handling for age validation
        if field_name == 'age':
            try:
                age_int = int(field_value)
                if not (1 <= age_int <= 120):
                    logger.error(f"Invalid age: {field_value}")
                    return None
                update_data[field_name] = age_int
            except ValueError:
                logger.error(f"Age must be a number: {field_value}")
                return None
            
        result = supabase_client.table('patients')\
            .update(update_data)\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Updated patient {field_name}: {patient_id} -> {field_value}")
            return result.data[0]
        else:
            logger.error(f"Failed to update {field_name}: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error updating {field_name}: {e}")
        return None

async def complete_profile_update(patient_id: str) -> Dict[str, Any]:
    """
    Mark profile update as complete and return full profile.
    
    Args:
        patient_id: Patient's ID
    
    Returns:
        Complete patient record dictionary
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        result = supabase_client.table('patients')\
            .update({
                'onboarding_completed': True,
                'onboarding_step': 'completed',
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Completed profile update for patient: {patient_id}")
            return result.data[0]
        else:
            logger.error(f"Failed to complete profile update: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error completing profile update: {e}")
        return None

async def reset_patient_onboarding(patient_id: str) -> Dict[str, Any]:
    """
    Reset patient onboarding for fresh start.
    
    Args:
        patient_id: Patient's ID
    
    Returns:
        Reset patient record dictionary
    """
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        result = supabase_client.table('patients')\
            .update({
                'onboarding_step': 'email',
                'onboarding_completed': False,
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Reset onboarding for patient: {patient_id}")
            return result.data[0]
        else:
            logger.error(f"Failed to reset onboarding: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error resetting onboarding: {e}")
        return None

async def update_patient_age(patient_id: str, age: int) -> Dict[str, Any]:
    """Update patient's age."""
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        result = supabase_client.table('patients')\
            .update({'age': age, 'onboarding_step': 'gender', 'updated_at': datetime.now().isoformat()})\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Updated patient age: {patient_id} -> {age}")
            return result.data[0]
        else:
            logger.error(f"Failed to update age: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error updating age: {e}")
        return None

async def update_patient_gender(patient_id: str, gender: str) -> Dict[str, Any]:
    """Update patient's gender."""
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        result = supabase_client.table('patients')\
            .update({'gender': gender, 'onboarding_step': 'awaiting_email', 'updated_at': datetime.now().isoformat()})\
            .eq('id', patient_id)\
            .execute()
            
        if result.data and len(result.data) > 0:
            logger.info(f"Updated patient gender: {patient_id} -> {gender}")
            return result.data[0]
        else:
            logger.error(f"Failed to update gender: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error updating gender: {e}")
        return None







async def create_appointment_request(patient_id: str, requested_date: datetime, requested_time: str, reason: str = None) -> Dict[str, Any]:
    """Create a custom appointment request."""
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        request_data = {
            'patient_id': patient_id,
            'requested_date': requested_date.isoformat(),
            'requested_time': requested_time,
            'reason': reason,
            'status': 'pending'
        }
        
        result = supabase_client.table('appointment_requests').insert(request_data).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"Created appointment request for patient: {patient_id}")
            return result.data[0]
        else:
            logger.error(f"Failed to create appointment request: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating appointment request: {e}")
        return None

async def get_patient_onboarding_status(patient_id: str) -> Dict[str, Any]:
    """
    Get patient's current onboarding status with retry logic.
    
    Args:
        patient_id: Patient's ID
    
    Returns:
        Patient onboarding status dictionary
    """
    async def _get_status_operation():
        supabase_client = get_supabase_client()
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return None
            
        # Get patient onboarding status
        result = supabase_client.table('patients')\
            .select('onboarding_step, onboarding_completed, age, gender')\
            .eq('id', patient_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            logger.warning(f"Patient onboarding status not found: {patient_id}")
            return None
    
    try:
        return await execute_with_retry(_get_status_operation)
    except Exception as e:
        logger.error(f"Error getting patient onboarding status after retries: {e}")
        return None

# Test function to check database connection
async def test_connection() -> bool:
    """Test the Supabase connection."""
    try:
        supabase_client = get_supabase_client()
        if not supabase_client:
            return False
            
        result = supabase_client.table('patients').select('count').execute()
        logger.info("Supabase connection successful")
        return True
        
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False 