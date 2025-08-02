import re
import google.generativeai as genai
import json
import os
import logging
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv

import httpx  # For API requests

logger = logging.getLogger(__name__)

# Global model variable
model = None

def get_gemini_model():
    """Get Gemini model with lazy loading and proper error handling."""
    global model
    
    if model is None:
        load_dotenv()  # Ensure environment variables are loaded
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            return None
    
    return model

async def analyze_message(message: str, conversation_history: list = None, current_step: str = None, is_onboarding_complete: bool = False) -> Dict[str, Any]:
    """
    Analyzes user message to determine intent and extract entities.
    
    Args:
        message: The user's WhatsApp message
        conversation_history: Previous messages (optional)
        current_step: Current onboarding step for context-aware analysis
        is_onboarding_complete: Whether user has completed onboarding
    
    Returns:
        Dict with 'intent' and 'entities' keys
    """
    try:
        gemini_model = get_gemini_model()
        
        if not gemini_model:
            logger.warning("Gemini model not available, using fallback")
            return _get_fallback_response(message, current_step, is_onboarding_complete)
        
        prompt = f"""
You are an AI triage assistant for a specialized Hair & Trichology Clinic. Your job is to analyze the user's message and determine their primary INTENT.

CONTEXT:
- The user is at this step of the conversation: "{current_step}"

POSSIBLE INTENTS:
- `dermatology_query`: The user is asking ANY question about hair.
- `request_booking`: The user wants to book a NEW appointment.
- `request_reschedule`: The user wants to CHANGE an existing appointment.
- `request_cancellation`: The user wants to CANCEL an appointment.
- `select_choice`: The user is replying with a number (e.g., "1") to a question you just asked. This is the intent for ANY numeric choice.
- `provide_time`: The user is providing a time for their appointment (e.g., "4 pm", "15:30").
- `greeting`: A simple "hello," "hi," etc.
- `unknown`: The intent cannot be determined.

User Message: "{message}"

CRITICAL: You MUST return a valid JSON object with BOTH an "intent" and an "entities" key. The "entities" key can be an empty object.

Example Response Format:
{{"intent": "greeting", "entities": {{}}}}
"""

        # Enhanced retry logic for Gemini 2.5 Flash
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await gemini_model.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=300,  # Increased for better completion
                        candidate_count=1,
                    )
                )
                
                # Enhanced response parsing with aggressive cleaning
                response_text = response.text.strip() if response.text else ""
                logger.info(f"Gemini raw response (attempt {attempt + 1}): {response_text}")
                
                if not response_text:
                    logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")
                    if attempt == max_retries - 1:
                        logger.error("All Gemini attempts failed with empty responses, using fallback")
                        return _get_fallback_response(message, current_step, is_onboarding_complete)
                    continue
                
                # Aggressive JSON cleaning for Gemini 2.5 Flash
                cleaned_text = _clean_gemini_response(response_text)
                
                if not cleaned_text:
                    logger.warning(f"Response cleaning resulted in empty text (attempt {attempt + 1})")
                    if attempt == max_retries - 1:
                        return _get_fallback_response(message, current_step, is_onboarding_complete)
                    continue
            
                # Try to parse JSON
                try:
                    result = json.loads(cleaned_text)
                    
                    # Validate required structure
                    if not isinstance(result, dict) or 'intent' not in result or 'entities' not in result:
                        logger.warning(f"Invalid JSON structure (attempt {attempt + 1}): {result}")
                        if attempt == max_retries - 1:
                            return _get_fallback_response(message, current_step, is_onboarding_complete)
                        continue
                    
                    # Ensure all entity fields exist
                    required_entities = {
                        'slot_number': None, 'profile_choice': None, 'email': None, 'age': None,
                        'gender': None, 'blood_group': None, 'current_symptoms': None, 'allergies': None,
                        'date_preference': None, 'time_preference': None, 'custom_request': None
                    }
                    
                    if 'entities' not in result:
                        result['entities'] = {}
                    
                    result['entities'].update({k: v for k, v in required_entities.items() if k not in result['entities']})
                    
                    logger.info(f"Gemini parsed result (attempt {attempt + 1}): {result}")
                    return result
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error (attempt {attempt + 1}): {e}")
                    logger.warning(f"Cleaned response was: {cleaned_text}")
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to parse Gemini JSON after {max_retries} attempts: {e}")
                        return _get_fallback_response(message, current_step, is_onboarding_complete)
                    continue
                
            except Exception as e:
                logger.warning(f"Error calling Gemini API (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Error calling Gemini API after {max_retries} attempts: {e}")
                    return _get_fallback_response(message, current_step, is_onboarding_complete)
                continue
        
        # This should not be reached, but just in case
        return _get_fallback_response(message, current_step, is_onboarding_complete)
            
    except Exception as e:
        logger.error(f"Unexpected error in analyze_message: {e}")
        return _get_fallback_response(message, current_step, is_onboarding_complete)

def _clean_gemini_response(response_text: str) -> str:
    """
    Aggressively clean Gemini 2.5 Flash responses to extract valid JSON.
    """
    if not response_text:
        return ""
    
    # Remove markdown formatting
    if response_text.startswith('```json'):
        response_text = response_text.replace('```json', '').replace('```', '').strip()
    elif response_text.startswith('```'):
        response_text = response_text.replace('```', '').strip()
    
    # Remove any text before first {
    start_idx = response_text.find('{')
    if start_idx == -1:
        logger.warning("No opening brace found in response")
        return ""
    
    # Remove any text after last }
    end_idx = response_text.rfind('}')
    if end_idx == -1:
        logger.warning("No closing brace found in response")
        return ""
    
    # Extract JSON portion
    json_portion = response_text[start_idx:end_idx + 1]
    
    # Additional cleaning for common Gemini 2.5 Flash issues
    json_portion = json_portion.strip()
    
    # Handle incomplete JSON by trying to fix common issues
    if json_portion.count('{') != json_portion.count('}'):
        logger.warning("Mismatched braces detected, attempting to fix")
        # Try to balance braces
        open_count = json_portion.count('{')
        close_count = json_portion.count('}')
        if open_count > close_count:
            json_portion += '}' * (open_count - close_count)
    
    # Handle incomplete strings
    if json_portion.count('"') % 2 != 0:
        logger.warning("Odd number of quotes detected, attempting to fix")
        json_portion += '"'
    
    return json_portion

def _get_fallback_response(message: str, current_step: str = None, is_onboarding_complete: bool = False) -> Dict[str, Any]:
    """
    Enhanced context-aware fallback response when Gemini is not available.
    Uses keyword-based intent detection with context-sensitive decision making.
    """
    # Handle the specific step of awaiting a custom date.
    # Any input here is assumed to be the user's date preference.
    if current_step == 'awaiting_custom_date':
        logger.info("Fallback triggered in 'awaiting_custom_date' step. Treating message as date preference.")
        return {
            "intent": "request_custom_date",
            "entities": {
                "slot_number": None, "profile_choice": None, "email": None, "age": None,
                "gender": None, "blood_group": None, "current_symptoms": None, "allergies": None,
                "date_preference": message.strip(),  # Treat the whole message as the date
                "time_preference": None, "custom_request": None
            }
        }
    
    message_lower = message.lower().strip()
    
    # Check for email patterns
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, message)
    
    # Enhanced custom date/time patterns
    days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    time_patterns = ['am', 'pm', 'morning', 'afternoon', 'evening', 'night']
    date_words = ['tomorrow', 'today', 'next', 'this']
    
    # Check for custom date requests
    has_day = any(day in message_lower for day in days_of_week)
    has_time = any(time in message_lower for time in time_patterns) or re.search(r'\d{1,2}[:.]?\d{0,2}\s*(am|pm)', message_lower)
    has_date_word = any(word in message_lower for word in date_words)
    has_other_request = any(word in message_lower for word in ['other', 'different', 'custom', 'change'])
    
    # Age pattern
    age_match = re.search(r'\b(\d{1,3})\b', message)
    
    # Blood group pattern
    blood_groups = ['a+', 'a-', 'b+', 'b-', 'ab+', 'ab-', 'o+', 'o-']
    blood_group_match = None
    for bg in blood_groups:
        if bg in message_lower:
            blood_group_match = bg.upper()
            break
    
    # Gender patterns
    gender_words = {'male': 'Male', 'female': 'Female', 'other': 'Other', 'm': 'Male', 'f': 'Female'}
    gender_match = None
    for word, gender in gender_words.items():
        if word in message_lower:
            gender_match = gender
            break
    
    # Context-aware number interpretation
    number_match = re.search(r'^(\d+)$', message_lower.strip())
    number_value = number_match.group(1) if number_match else None
    
    # Enhanced symptoms detection
    symptom_keywords = ['pain', 'ache', 'fever', 'cough', 'headache', 'hurt', 'sick', 'feel', 'symptom', 'today', 'currently']
    has_symptoms = any(keyword in message_lower for keyword in symptom_keywords)
    
    # Profile management keywords
    profile_keywords = ['profile', 'update', 'change', 'modify', 'information']
    has_profile_request = any(keyword in message_lower for keyword in profile_keywords)
    
    # Quick booking keywords
    quick_booking_keywords = ['quick', 'fast', 'use existing', 'same info']
    has_quick_booking = any(keyword in message_lower for keyword in quick_booking_keywords)
    
    # Keep/maintain keywords
    keep_keywords = ['keep', 'maintain', 'same', 'no change', 'dont change', "don't change"]
    has_keep_request = any(keyword in message_lower for keyword in keep_keywords)
    
    # Base entity structure
    base_entities = {
        "slot_number": None,
        "profile_choice": None,
        "email": None,
        "age": None,
        "gender": None,
        "blood_group": None,
        "current_symptoms": None,
        "allergies": None,
        "date_preference": None,
        "time_preference": None,
        "custom_request": None
    }
    
    # CONTEXT-AWARE INTENT DETERMINATION
    logger.info(f"Fallback context: current_step='{current_step}', message='{message}', onboarding_complete={is_onboarding_complete}")
    
    # Handle "Other" specifically - this should ALWAYS be custom date request
    if message_lower in ['other', 'others', 'different']:
        logger.info("Detected 'other' - treating as request_custom_date")
        return {
            "intent": "request_custom_date",
            "entities": {**base_entities, "custom_request": "other"}
        }
    
    # Handle numbers based on context
    if number_value:
        # Context 1: If we're in current_symptoms step and showing slots, treat numbers 1-5 as slot selection
        if current_step == 'current_symptoms':
            if number_value in ['1', '2', '3', '4', '5']:
                logger.info(f"Number '{number_value}' in current_symptoms context - treating as slot selection")
                return {
                    "intent": "select_slot",
                    "entities": {**base_entities, "slot_number": number_value}
                }
        
        # Context 2: If we're greeting a returning user, treat numbers 1-4 as profile choices
        elif is_onboarding_complete and current_step in ['start', None, 'completed']:
            if number_value in ['1', '2', '3', '4']:
                logger.info(f"Number '{number_value}' in greeting context - treating as profile choice")
                return {
                    "intent": "profile_choice",
                    "entities": {**base_entities, "profile_choice": number_value}
                }
        
        # Context 3: Age input
        elif current_step == 'age':
            age_val = int(number_value)
            if 1 <= age_val <= 120:
                return {
                    "intent": "provide_age",
                    "entities": {**base_entities, "age": number_value}
                }
    
    # Handle keep requests in update contexts
    if has_keep_request and current_step and current_step.startswith('update_'):
        logger.info(f"Keep request in update context: {current_step}")
        return {
            "intent": "keep_current_value",
            "entities": base_entities
        }
    
    # Email detection
    if email_match:
        return {
            "intent": "provide_email",
            "entities": {**base_entities, "email": email_match.group()}
        }
    
    # Gender detection
    if gender_match and current_step == 'gender':
        return {
            "intent": "provide_gender",
            "entities": {**base_entities, "gender": gender_match}
        }
    
    # Blood group detection
    if blood_group_match and current_step == 'blood_group':
        return {
            "intent": "provide_blood_group",
            "entities": {**base_entities, "blood_group": blood_group_match}
        }
    
    # Enhanced custom date/time recognition
    if (has_day and has_time) or (has_date_word and has_time) or has_other_request:
        date_pref = None
        time_pref = None
        custom_req = None
        
        if has_other_request:
            custom_req = "different timing"
        
        # Extract date preference
        for day in days_of_week:
            if day in message_lower:
                date_pref = day.capitalize()
                break
        
        if not date_pref:
            for date_word in date_words:
                if date_word in message_lower:
                    date_pref = date_word
                    break
        
        # Extract time preference
        time_match = re.search(r'(\d{1,2}[:.]?\d{0,2}\s*(am|pm|AM|PM))', message)
        if time_match:
            time_pref = time_match.group(1)
        else:
            for time_pattern in time_patterns:
                if time_pattern in message_lower:
                    time_pref = time_pattern
                    break
        
        logger.info(f"Custom date detected: date_pref='{date_pref}', time_pref='{time_pref}', custom_req='{custom_req}'")
        return {
            "intent": "request_custom_date",
            "entities": {
                **base_entities,
                "date_preference": date_pref,
                "time_preference": time_pref,
                "custom_request": custom_req
            }
        }
    
    # Profile management intents
    if has_quick_booking:
        return {
            "intent": "quick_book_with_profile",
            "entities": base_entities
        }
    elif has_profile_request:
        return {
            "intent": "update_profile_only",
            "entities": base_entities
        }
    
    # Allergy detection (context-aware)
    if current_step == 'allergies' or current_step == 'update_allergies':
        allergy_value = "none" if message_lower in ['none', 'no', 'nothing', 'nil'] else message.strip()
        return {
            "intent": "provide_allergies",
            "entities": {**base_entities, "allergies": allergy_value}
        }
    
    # Symptom detection (only if in symptoms context and not navigation)
    if current_step == 'current_symptoms' and has_symptoms and not number_value:
        logger.info(f"Symptoms detected in current_symptoms context: {message}")
        return {
            "intent": "provide_current_symptoms",
            "entities": {**base_entities, "current_symptoms": message.strip()}
        }
    
    # Greeting detection
    if message_lower in ['hi', 'hello', 'hey', 'start']:
        return {
            "intent": "greeting",
            "entities": base_entities
        }
    
    # Booking intent detection
    if any(phrase in message_lower for phrase in ['book appointment', 'book', 'appointment', 'yes']):
        return {
            "intent": "start_onboarding",
            "entities": base_entities
        }
    
    # Default fallback
    logger.warning(f"Fallback couldn't determine intent for: '{message}' in context '{current_step}'")
    return {
        "intent": "unknown",
        "entities": base_entities
    }

def extract_slot_number(message: str) -> int:
    """
    Extract slot number from user message.
    """
    try:
        # Try to parse as integer
        return int(message.strip())
    except ValueError:
        # Look for numbers in the message
        import re
        numbers = re.findall(r'\d+', message)
        if numbers:
            return int(numbers[0])
        return None

async def generate_dermatology_response(query: str) -> str:
    """
    Queries the Docser API to get answers for hair health questions and cleans the response.
    """
    logger.info(f"Querying Docser API for: '{query}'")
    
    api_url = os.getenv("DOCSER_API_URL")
    api_token = os.getenv("DOCSER_API_TOKEN")
    org_id = os.getenv("DOCSER_ORG_ID")
    collection_name = os.getenv("DOCSER_COLLECTION_NAME")

    if not all([api_url, api_token, org_id, collection_name]):
        logger.error("Docser API environment variables are not fully configured.")
        return "I'm sorry, my connection to the knowledge base is currently unavailable. Please try again later."

    payload = {
        'question': query,
        'collectionName': collection_name,
        'jsonData': '',
        'documentName': '',
        'usertype': 'team',
        'chat_context': ''
    }
    
    headers = {
        'x-orgId': org_id,
        'X-Api-Token': api_token,
        'X-Api-Org': org_id,
    }

    timeout_config = httpx.Timeout(10.0, read=100.0)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, data=payload, timeout=timeout_config)
            response.raise_for_status()

            try:
                json_response = response.json()
                api_answer = json_response.get('response', str(json_response))
            except (ValueError, json.JSONDecodeError):
                api_answer = response.text
            
            if not api_answer or not api_answer.strip():
                 logger.warning("Docser API returned an empty response.")
                 return "I couldn't find a specific answer for your question at the moment. Could you please rephrase it?"

            logger.info("Successfully received response from Docser API. Cleaning sources...")

            # --- FINAL, MORE GENERIC CLEANING LOGIC ---
            # This regex finds any markdown link followed by "Page(s):" and any numbers/commas/hyphens.
            citation_pattern = r'\s*\[[^\]]+\]\((https?|ftp)://[^\s/$.?#].[^\s]*\)\s*Pages?:\s*[\d,\s\-]+\.'
            cleaned_answer = re.sub(citation_pattern, '', api_answer, flags=re.IGNORECASE)
            # --- END OF FINAL LOGIC ---

            return cleaned_answer.strip()

    except httpx.ReadTimeout:
        logger.error(f"ReadTimeout occurred when calling Docser API. The server took too long to respond.")
        return "I'm sorry, the knowledge base is taking too long to respond. Please try again in a moment."
    except httpx.ConnectTimeout:
        logger.error(f"ConnectTimeout occurred. Could not connect to the Docser API server.")
        return "I'm sorry, I'm unable to connect to the knowledge base right now. Please check back later."
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred when calling Docser API: {e.response.status_code} - {e.response.text}")
        return "I'm sorry, I encountered an error while retrieving information. The support team has been notified."
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_dermatology_response: {e}", exc_info=True)
        return "I'm experiencing a technical issue. Please try asking your question again in a few moments." 