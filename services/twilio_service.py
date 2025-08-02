from twilio.rest import Client
import os
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Twilio client
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')

if not account_sid or not auth_token or not twilio_phone:
    logger.warning("Twilio credentials not found in environment variables")
    twilio_client = None
else:
    twilio_client = Client(account_sid, auth_token)

async def send_whatsapp_message(to_number: str, message_body: str) -> bool:
    """
    Sends a WhatsApp message, automatically splitting it into multiple parts
    if it exceeds the character limit.
    """
    if not twilio_client:
        logger.error("Twilio client not initialized")
        return False

    # WhatsApp's character limit is 1600. We'll use 1500 to be safe.
    MAX_LENGTH = 1500
    
    try:
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        from_number = f'whatsapp:{twilio_phone}'

        # If the message is short enough, send it in one go.
        if len(message_body) <= MAX_LENGTH:
            message = twilio_client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_number
            )
            logger.info(f"WhatsApp message sent successfully. SID: {message.sid}")
            return True

        # If the message is too long, split it into chunks.
        else:
            logger.info("Message exceeds character limit. Splitting into multiple messages.")
            message_chunks = []
            current_chunk = ""
            
            # Split by newline to keep paragraphs together
            for line in message_body.split('\n'):
                # If adding the next line would exceed the limit, store the current chunk and start a new one.
                if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                    message_chunks.append(current_chunk)
                    current_chunk = line
                # Otherwise, add the line to the current chunk.
                else:
                    current_chunk += '\n' + line
            
            # Add the last remaining chunk to the list.
            if current_chunk:
                message_chunks.append(current_chunk)
            
            # Send each chunk as a separate message
            for i, chunk in enumerate(message_chunks):
                if chunk.strip(): # Ensure we don't send empty messages
                    twilio_client.messages.create(
                        body=chunk.strip(),
                        from_=from_number,
                        to=to_number
                    )
                    logger.info(f"Sent chunk {i+1}/{len(message_chunks)}.")
                    # Add a small delay between messages to ensure they arrive in order
                    await asyncio.sleep(1.5)
            
            logger.info("All message chunks sent successfully.")
            return True

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return False

async def send_sms_message(to_number: str, message_body: str) -> bool:
    """
    Send an SMS message using Twilio API.
    
    Args:
        to_number: Recipient's phone number (with country code)
        message_body: Message content to send
    
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        if not twilio_client:
            logger.error("Twilio client not initialized")
            return False
        
        # Send SMS
        message = twilio_client.messages.create(
            body=message_body,
            from_=twilio_phone,
            to=to_number
        )
        
        logger.info(f"SMS message sent successfully. SID: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending SMS message: {e}")
        return False

def get_message_status(message_sid: str) -> Optional[str]:
    """
    Get the status of a previously sent message.
    
    Args:
        message_sid: Twilio message SID
    
    Returns:
        Message status string or None if error
    """
    try:
        if not twilio_client:
            logger.error("Twilio client not initialized")
            return None
        
        message = twilio_client.messages(message_sid).fetch()
        return message.status
        
    except Exception as e:
        logger.error(f"Error getting message status: {e}")
        return None

def validate_phone_number(phone_number: str) -> bool:
    """
    Basic validation for phone number format.
    
    Args:
        phone_number: Phone number to validate
    
    Returns:
        True if valid format, False otherwise
    """
    import re
    
    # Remove any whitespace and special characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Check if it's a valid international format
    # Should start with + and have 7-15 digits
    if re.match(r'^\+\d{7,15}$', cleaned):
        return True
    
    # Check if it's a US number without country code
    if re.match(r'^\d{10}$', cleaned):
        return True
    
    return False

def format_phone_number(phone_number: str) -> str:
    """
    Format phone number to international format.
    
    Args:
        phone_number: Phone number to format
    
    Returns:
        Formatted phone number with country code
    """
    import re
    
    # Remove any whitespace and special characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # If it's already in international format
    if cleaned.startswith('+'):
        return cleaned
    
    # If it's a 10-digit US number, add US country code
    if re.match(r'^\d{10}$', cleaned):
        return f'+1{cleaned}'
    
    # If it's an 11-digit number starting with 1, add +
    if re.match(r'^1\d{10}$', cleaned):
        return f'+{cleaned}'
    
    # Return as-is if we can't determine format
    return phone_number

async def send_appointment_confirmation(phone_number: str, appointment_details: dict) -> bool:
    """
    Send appointment confirmation message.
    
    Args:
        phone_number: Patient's phone number
        appointment_details: Dictionary with appointment info
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Format the confirmation message
        message = f"✅ Appointment Confirmed!\n\n"
        message += f"📅 Date: {appointment_details.get('date', 'TBD')}\n"
        message += f"⏰ Time: {appointment_details.get('time', 'TBD')}\n"
        message += f"👨‍⚕️ Doctor: {appointment_details.get('doctor', 'Dr. Sunil Mishra')}\n"
        message += f"📍 Location: {appointment_details.get('location', 'Clinic')}\n\n"
        message += "Please arrive 15 minutes early. To reschedule, contact us 24h in advance.\n\n"
        message += "Thank you for choosing our clinic!"
        
        return await send_whatsapp_message(phone_number, message)
        
    except Exception as e:
        logger.error(f"Error sending appointment confirmation: {e}")
        return False

async def send_appointment_reminder(phone_number: str, appointment_details: dict) -> bool:
    """
    Send appointment reminder message.
    
    Args:
        phone_number: Patient's phone number
        appointment_details: Dictionary with appointment info
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Format the reminder message
        message = f"⏰ Appointment Reminder\n\n"
        message += f"You have an appointment tomorrow:\n"
        message += f"📅 Date: {appointment_details.get('date', 'TBD')}\n"
        message += f"⏰ Time: {appointment_details.get('time', 'TBD')}\n"
        message += f"👨‍⚕️ Doctor: {appointment_details.get('doctor', 'Dr. Sunil Mishra')}\n\n"
        message += "Please arrive 15 minutes early. If you need to reschedule, please contact us immediately.\n\n"
        message += "See you soon!"
        
        return await send_whatsapp_message(phone_number, message)
        
    except Exception as e:
        logger.error(f"Error sending appointment reminder: {e}")
        return False

# Test function
async def test_connection() -> bool:
    """Test the Twilio connection."""
    try:
        if not twilio_client:
            return False
        
        # Try to get account info to test connection
        account = twilio_client.api.account.fetch()
        logger.info(f"Twilio connection successful. Account: {account.friendly_name}")
        return True
        
    except Exception as e:
        logger.error(f"Twilio connection test failed: {e}")
        return False 