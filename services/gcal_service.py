from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Google Calendar API scope - enhanced for domain-wide delegation
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

# Initialize Google Calendar service
calendar_service = None

def get_calendar_service(subject_email: str = None):
    """
    Get Google Calendar service with optional domain-wide delegation.
    
    Args:
        subject_email: Email address to impersonate (for domain-wide delegation)
    
    Returns:
        Google Calendar service instance or None
    """
    global calendar_service
    
    if calendar_service is None:
        load_dotenv()  # Ensure environment variables are loaded
        
        # Try to get service account credentials from environment variable
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')  # Optional: specific calendar ID
        domain_wide_delegation = os.getenv('GOOGLE_DOMAIN_WIDE_DELEGATION', 'false').lower() == 'true'
        
        if not service_account_json:
            logger.warning("Google Calendar not configured: GOOGLE_SERVICE_ACCOUNT_JSON not found in environment variables")
            logger.info("Google Calendar features will be disabled. Set GOOGLE_SERVICE_ACCOUNT_JSON to enable.")
            return None
        
        try:
            # Parse the service account JSON from environment variable
            service_account_info = json.loads(service_account_json)
            
            # Create credentials from service account info
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            
            # Apply domain-wide delegation if configured and subject_email is provided
            if domain_wide_delegation and subject_email:
                logger.info(f"Using domain-wide delegation with subject: {subject_email}")
                credentials = credentials.with_subject(subject_email)
            
            # Build the calendar service
            calendar_service = build('calendar', 'v3', credentials=credentials)
            logger.info("Google Calendar service initialized successfully with service account")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {e}")
            return None
    
    return calendar_service

async def create_calendar_event(
    summary: str, 
    start_time: str, 
    end_time: str, 
    attendee_email: Optional[str] = None,
    description: str = "",
    location: str = "Clinic",
    organizer_email: str = None
) -> Optional[Dict[str, Any]]:
    """
    Create a Google Calendar event with enhanced invitation support.
    
    Args:
        summary: Event title/summary
        start_time: Start time in ISO format (e.g., "2024-08-01T10:00:00Z")
        end_time: End time in ISO format (e.g., "2024-08-01T10:30:00Z")
        attendee_email: Email of attendee (patient)
        description: Event description
        location: Event location
        organizer_email: Email of the organizer (doctor/clinic)
    
    Returns:
        Created event dictionary with invitation status
    """
    try:
        # Check if domain-wide delegation is enabled
        domain_wide_delegation = os.getenv('GOOGLE_DOMAIN_WIDE_DELEGATION', 'false').lower() == 'true'
        default_organizer = os.getenv('GOOGLE_CALENDAR_ORGANIZER_EMAIL')
        
        # Use provided organizer email or default
        effective_organizer = organizer_email or default_organizer
        
        # Get service with domain-wide delegation if available
        if domain_wide_delegation and effective_organizer:
            service = get_calendar_service(subject_email=effective_organizer)
            logger.info(f"Using domain-wide delegation with organizer: {effective_organizer}")
        else:
            service = get_calendar_service()
        
        if not service:
            logger.warning("Calendar service not available - skipping calendar event creation")
            return {"status": "skipped", "reason": "calendar_service_not_configured"}
        
        # Parse datetime strings to ensure proper formatting
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError as e:
            logger.error(f"Invalid datetime format: {e}")
            return None
        
        # Enhanced description with appointment details
        enhanced_description = f"{description}\n\n"
        if attendee_email:
            enhanced_description += f"Patient Email: {attendee_email}\n"
        enhanced_description += f"Appointment created via Doctor AI WhatsApp Assistant\n"
        enhanced_description += f"Created at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        # Prepare event data with full invitation support
        event = {
            'summary': summary,
            'location': location,
            'description': enhanced_description,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24 hours before
                    {'method': 'popup', 'minutes': 30},        # 30 minutes before
                ],
            },
        }
        
        # Add organizer information if available
        if effective_organizer:
            event['organizer'] = {
                'email': effective_organizer,
                'displayName': "Dr. Sunil Mishra's Clinic"
            }
        
        # Get calendar ID (use primary calendar if not specified)
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
        
        # Strategy 1: Try with attendees (works with domain-wide delegation)
        try:
            if attendee_email:
                event['attendees'] = [
                    {
                        'email': attendee_email,
                        'responseStatus': 'needsAction'  # Invitation pending
                    }
                ]
                
                # Set sendUpdates to send email invitations
                created_event = service.events().insert(
                    calendarId=calendar_id, 
                    body=event,
                    sendUpdates='all'  # Send email invitations
                ).execute()
                
                logger.info(f"Calendar event created successfully with email invitation: {created_event.get('id')}")
                
                # Try to send email notification as well
                email_sent = await send_appointment_email_notification(
                    attendee_email=attendee_email,
                    organizer_email=effective_organizer,
                    summary=summary,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    location=location,
                    description=description,
                    calendar_link=created_event.get('htmlLink')
                )
                
                return {
                    "status": "success",
                    "method": "with_attendee_invitation",
                    "event_id": created_event.get('id'),
                    "html_link": created_event.get('htmlLink'),
                    "summary": created_event.get('summary'),
                    "start_time": created_event.get('start', {}).get('dateTime'),
                    "end_time": created_event.get('end', {}).get('dateTime'),
                    "attendee_email": attendee_email,
                    "invitation_sent": True,
                    "email_notification_sent": email_sent
                }
                
        except HttpError as permission_error:
            error_message = str(permission_error)
            if "forbiddenForServiceAccounts" in error_message or "Forbidden" in error_message:
                logger.warning(f"Permission issue with attendee invitations: {permission_error}")
                logger.info("Falling back to event creation without automatic invitations...")
                
                # Strategy 2: Create event without attendees, use email notification
                if 'attendees' in event:
                    del event['attendees']
                
                created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
                
                # Generate "Add to Calendar" links for the patient
                calendar_links = generate_calendar_links(
                    summary=summary,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    description=enhanced_description,
                    location=location
                )
                
                # Send custom email notification instead
                email_sent = await send_appointment_email_notification(
                    attendee_email=attendee_email,
                    organizer_email=effective_organizer,
                    summary=summary,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    location=location,
                    description=description,
                    calendar_link=created_event.get('htmlLink'),
                    calendar_links=calendar_links
                )
                
                logger.info(f"Calendar event created with email notification fallback: {created_event.get('id')}")
                return {
                    "status": "success",
                    "method": "without_attendee_with_email",
                    "event_id": created_event.get('id'),
                    "html_link": created_event.get('htmlLink'),
                    "summary": created_event.get('summary'),
                    "start_time": created_event.get('start', {}).get('dateTime'),
                    "end_time": created_event.get('end', {}).get('dateTime'),
                    "calendar_links": calendar_links,
                    "attendee_email": attendee_email,
                    "invitation_sent": False,
                    "email_notification_sent": email_sent,
                    "note": "Calendar event created with email notification due to permission limitations"
                }
            else:
                raise permission_error
        
        # Strategy 3: Create basic event without attendees (last resort)
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        calendar_links = generate_calendar_links(
            summary=summary,
            start_dt=start_dt,
            end_dt=end_dt,
            description=enhanced_description,
            location=location
        )
        
        logger.info(f"Basic calendar event created: {created_event.get('id')}")
        return {
            "status": "success",
            "method": "basic_event",
            "event_id": created_event.get('id'),
            "html_link": created_event.get('htmlLink'),
            "summary": created_event.get('summary'),
            "start_time": created_event.get('start', {}).get('dateTime'),
            "end_time": created_event.get('end', {}).get('dateTime'),
            "calendar_links": calendar_links,
            "attendee_email": attendee_email,
            "invitation_sent": False,
            "email_notification_sent": False
        }
        
    except HttpError as error:
        logger.error(f"Google Calendar API error: {error}")
        return {
            "status": "error",
            "reason": str(error),
            "fallback_available": True
        }
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return None

async def update_calendar_event(
    event_id: str,
    summary: str = None,
    start_time: str = None,
    end_time: str = None,
    attendee_email: str = None,
    description: str = None,
    location: str = None
) -> Optional[Dict[str, Any]]:
    """
    Update an existing Google Calendar event.
    
    Args:
        event_id: ID of the event to update
        summary: New event title (optional)
        start_time: New start time (optional)
        end_time: New end time (optional)
        attendee_email: New attendee email (optional)
        description: New description (optional)
        location: New location (optional)
    
    Returns:
        Updated event dictionary or None if failed
    """
    try:
        global calendar_service
        
        if not calendar_service:
            calendar_service = initialize_calendar_service()
        
        if not calendar_service:
            logger.error("Calendar service not available")
            return None
        
        # First, get the existing event
        event = calendar_service.events().get(
            calendarId='primary', 
            eventId=event_id
        ).execute()
        
        # Update only the provided fields
        if summary:
            event['summary'] = summary
        if start_time:
            event['start']['dateTime'] = start_time
        if end_time:
            event['end']['dateTime'] = end_time
        if description:
            event['description'] = description
        if location:
            event['location'] = location
        if attendee_email:
            event['attendees'] = [{'email': attendee_email}]
        
        # Update the event
        updated_event = calendar_service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=event
        ).execute()
        
        logger.info(f"Calendar event updated: {event_id}")
        return updated_event
        
    except HttpError as error:
        logger.error(f"Google Calendar API error: {error}")
        return None
    except Exception as e:
        logger.error(f"Error updating calendar event: {e}")
        return None

async def delete_calendar_event(event_id: str) -> bool:
    """
    Delete a Google Calendar event.
    
    Args:
        event_id: ID of the event to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        global calendar_service
        
        if not calendar_service:
            calendar_service = initialize_calendar_service()
        
        if not calendar_service:
            logger.error("Calendar service not available")
            return False
        
        calendar_service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
        
        logger.info(f"Calendar event deleted: {event_id}")
        return True
        
    except HttpError as error:
        logger.error(f"Google Calendar API error: {error}")
        return False
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        return False

async def get_calendar_events(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    max_results: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Get calendar events within a time range.
    
    Args:
        start_time: Start time in ISO format (defaults to now)
        end_time: End time in ISO format (defaults to 1 week from now)
        max_results: Maximum number of events to return
    
    Returns:
        Dictionary with events list or None if failed
    """
    try:
        service = get_calendar_service()
        
        if not service:
            logger.warning("Calendar service not available")
            return None
        
        # Set default time range if not provided
        if not start_time:
            start_time = datetime.utcnow().isoformat() + 'Z'
        if not end_time:
            end_dt = datetime.utcnow() + timedelta(weeks=1)
            end_time = end_dt.isoformat() + 'Z'
        
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        return {
            "status": "success",
            "events": events,
            "count": len(events)
        }
        
    except HttpError as error:
        logger.error(f"Error getting calendar events: {error}")
        return None
    except Exception as e:
        logger.error(f"Error getting calendar events: {e}")
        return None

def format_datetime_for_calendar(dt_string: str) -> str:
    """
    Format datetime string for Google Calendar API.
    
    Args:
        dt_string: Datetime string in various formats
    
    Returns:
        Properly formatted datetime string for Google Calendar
    """
    try:
        # Parse the datetime string
        if dt_string.endswith('Z'):
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        elif '+' in dt_string or dt_string.endswith(('Z', '+00:00')):
            dt = datetime.fromisoformat(dt_string)
        else:
            dt = datetime.fromisoformat(dt_string)
        
        # Convert to the desired format for Google Calendar
        return dt.isoformat()
        
    except Exception as e:
        logger.error(f"Error formatting datetime: {e}")
        return dt_string

async def check_calendar_availability(start_time: str, end_time: str) -> bool:
    """
    Check if a time slot is available in the calendar.
    
    Args:
        start_time: Start time in ISO format
        end_time: End time in ISO format
    
    Returns:
        True if available, False if busy
    """
    try:
        global calendar_service
        
        if not calendar_service:
            calendar_service = initialize_calendar_service()
        
        if not calendar_service:
            logger.warning("Calendar service not available for availability check")
            return True  # Assume available if can't check
        
        # Check for conflicting events
        events = await get_calendar_events(start_time, end_time)
        
        # If there are any events in this time range, it's not available
        return len(events) == 0
        
    except Exception as e:
        logger.error(f"Error checking calendar availability: {e}")
        return True  # Assume available if error occurs

async def test_connection() -> Dict[str, Any]:
    """
    Test Google Calendar connection.
    
    Returns:
        Dictionary with connection status and details
    """
    try:
        service = get_calendar_service()
        
        if not service:
            return {
                "status": "disabled",
                "message": "Google Calendar service not configured",
                "details": "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable to enable Google Calendar"
            }
        
        # Try to access calendar list to test authentication
        calendar_list = service.calendarList().list(maxResults=1).execute()
        
        return {
            "status": "success",
            "message": "Google Calendar connected successfully",
            "details": f"Found {len(calendar_list.get('items', []))} calendar(s)",
            "service_account": True
        }
        
    except HttpError as error:
        return {
            "status": "error",
            "message": f"Google Calendar API error: {error}",
            "details": "Check service account permissions and calendar access"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Google Calendar connection failed: {str(e)}",
            "details": "Verify GOOGLE_SERVICE_ACCOUNT_JSON format and credentials"
        }

# Calendar service will be initialized lazily when needed 

def generate_calendar_links(summary: str, start_dt: datetime, end_dt: datetime, description: str = "", location: str = "") -> Dict[str, str]:
    """
    Generate "Add to Calendar" links for different calendar providers.
    
    Args:
        summary: Event title
        start_dt: Start datetime object
        end_dt: End datetime object  
        description: Event description
        location: Event location
    
    Returns:
        Dictionary with calendar provider links
    """
    try:
        # Format dates for calendar links
        start_str = start_dt.strftime('%Y%m%dT%H%M%SZ')
        end_str = end_dt.strftime('%Y%m%dT%H%M%SZ')
        
        # URL encode the details
        from urllib.parse import quote
        
        encoded_summary = quote(summary)
        encoded_description = quote(description)
        encoded_location = quote(location)
        
        # Generate links for different calendar providers
        google_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={encoded_summary}&dates={start_str}/{end_str}&details={encoded_description}&location={encoded_location}"
        
        outlook_link = f"https://outlook.live.com/calendar/0/deeplink/compose?subject={encoded_summary}&startdt={start_dt.isoformat()}&enddt={end_dt.isoformat()}&body={encoded_description}&location={encoded_location}"
        
        # Yahoo calendar link  
        yahoo_link = f"https://calendar.yahoo.com/?v=60&view=d&type=20&title={encoded_summary}&st={start_str}&dur=0030&desc={encoded_description}&in_loc={encoded_location}"
        
        # ICS file content for download
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Doctor AI//WhatsApp Assistant//EN
BEGIN:VEVENT
UID:{start_str}-doctor-ai@example.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{start_str}
DTEND:{end_str}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
END:VCALENDAR"""
        
        return {
            "google": google_link,
            "outlook": outlook_link,
            "yahoo": yahoo_link,
            "ics_content": ics_content
        }
        
    except Exception as e:
        logger.error(f"Error generating calendar links: {e}")
        return {} 

async def send_appointment_email_notification(
    attendee_email: str,
    organizer_email: str,
    summary: str,
    start_dt: datetime,
    end_dt: datetime,
    location: str,
    description: str,
    calendar_link: str = None,
    calendar_links: Dict[str, str] = None
) -> bool:
    """
    Send appointment confirmation email when calendar invitations can't be sent automatically.
    
    Args:
        attendee_email: Patient's email address
        organizer_email: Doctor/clinic email address
        summary: Appointment title
        start_dt: Start datetime
        end_dt: End datetime
        location: Appointment location
        description: Appointment description
        calendar_link: Direct Google Calendar link
        calendar_links: Dictionary of calendar provider links
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Check if email service is configured
        email_service_enabled = os.getenv('EMAIL_SERVICE_ENABLED', 'false').lower() == 'true'
        
        if not email_service_enabled:
            logger.info("Email service not enabled - skipping email notification")
            return False
        
        # Format appointment details
        formatted_date = start_dt.strftime('%A, %B %d, %Y')
        formatted_start_time = start_dt.strftime('%I:%M %p')
        formatted_end_time = end_dt.strftime('%I:%M %p')
        
        # Create email content
        subject = f"Your Consultation with Dr. Sunil Mishra is Confirmed"
        
        # HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Appointment Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .appointment-details {{ background-color: white; padding: 20px; margin: 20px 0; border-radius: 5px; }}
                .calendar-links {{ margin: 20px 0; }}
                .calendar-button {{ 
                    display: inline-block; 
                    background-color: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 5px;
                }}
                .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Consultation Confirmed!</h1>
                </div>
                
                <div class="content">
                    <p>Dear Patient,</p>
                    <p>Your consultation with Dr. Sunil Mishra has been successfully scheduled. We look forward to seeing you at our Hair & Trichology Clinic.</p>
                    
                    <div class="appointment-details">
                        <h3>📅 Consultation Details</h3>
                        <p><strong>Date:</strong> {formatted_date}</p>
                        <p><strong>Time:</strong> {formatted_start_time} - {formatted_end_time}</p>
                        <p><strong>Location:</strong> {location}</p>
                        <p><strong>Purpose:</strong> {summary}</p>
                        {f'<p><strong>Notes:</strong> {description}</p>' if description else ''}
                    </div>
                    
                    <div class="calendar-links">
                        <h3>📱 Add to Your Calendar</h3>
                        <p>Click one of the links below to add this appointment to your calendar:</p>
        """
        
        # Add calendar links if available
        if calendar_links:
            if calendar_links.get('google'):
                html_content += f'<a href="{calendar_links["google"]}" class="calendar-button">📅 Google Calendar</a>'
            if calendar_links.get('outlook'):
                html_content += f'<a href="{calendar_links["outlook"]}" class="calendar-button">📅 Outlook</a>'
            if calendar_links.get('yahoo'):
                html_content += f'<a href="{calendar_links["yahoo"]}" class="calendar-button">📅 Yahoo Calendar</a>'
        
        if calendar_link:
            html_content += f'<a href="{calendar_link}" class="calendar-button">🔗 View in Google Calendar</a>'
        
        html_content += f"""
                    </div>
                    
                    <div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #2196F3; margin: 20px 0;">
                        <h4>📋 Important Reminders</h4>
                        <ul>
                            <li>Please arrive 15 minutes early</li>
                            <li>Bring a valid ID and insurance card</li>
                            <li>If you need to reschedule, please contact us at least 24 hours in advance</li>
                        </ul>
                    </div>
                    
                    <p>If you have any questions or need to make changes to your appointment, please reply to this email or contact our clinic.</p>
                    
                    <p>We look forward to seeing you!</p>
                    
                    <p>Best regards,<br>The Team at Dr. Sunil Mishra's Clinic</p>
                </div>
                
                <div class="footer">
                    <p>This appointment was scheduled via the AI Assistant for Dr. Sunil Mishra's Clinic.</p>
                    <p>Email sent on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_content = f"""
        🎉 APPOINTMENT CONFIRMED!
        
        Dear Patient,
        
        Your consultation with Dr. Sunil Mishra has been successfully scheduled. We look forward to seeing you at our Hair & Trichology Clinic.
        
        📅 APPOINTMENT DETAILS:
        Date: {formatted_date}
        Time: {formatted_start_time} - {formatted_end_time}
        Location: {location}
        Purpose: {summary}
        {f'Notes: {description}' if description else ''}
        
        📱 ADD TO YOUR CALENDAR:
        {calendar_links.get('google', 'Google Calendar link not available') if calendar_links else 'Calendar links not available'}
        
        📋 IMPORTANT REMINDERS:
        • Please arrive 15 minutes early
        • Bring a valid ID and insurance card
        • If you need to reschedule, please contact us at least 24 hours in advance
        
        If you have any questions or need to make changes to your appointment, 
        please reply to this email or contact our clinic.
        
        We look forward to seeing you!
        
        Best regards,
        The Team at Dr. Sunil Mishra's Clinic
        
        ---
        This appointment was scheduled via the AI Assistant for Dr. Sunil Mishra's Clinic.
        Email sent on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}
        """
        
        # Try to send email using configured email service
        email_sent = await send_email(
            to_email=attendee_email,
            from_email=organizer_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
        
        if email_sent:
            logger.info(f"Appointment confirmation email sent to {attendee_email}")
            return True
        else:
            logger.warning(f"Failed to send appointment confirmation email to {attendee_email}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending appointment email notification: {e}")
        return False

async def send_email(to_email: str, from_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """
    Send email using configured email service (placeholder for integration).
    
    This function should be implemented based on your email service provider:
    - SendGrid
    - AWS SES
    - SMTP
    - Twilio SendGrid
    etc.
    
    Args:
        to_email: Recipient email
        from_email: Sender email
        subject: Email subject
        html_content: HTML email content
        text_content: Plain text email content
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get email service configuration
        email_provider = os.getenv('EMAIL_PROVIDER', 'none').lower()
        
        if email_provider == 'sendgrid':
            return await send_email_sendgrid(to_email, from_email, subject, html_content, text_content)
        elif email_provider == 'smtp':
            return await send_email_smtp(to_email, from_email, subject, html_content, text_content)
        else:
            logger.warning(f"No email provider configured (EMAIL_PROVIDER={email_provider})")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_email: {e}")
        return False

async def send_email_sendgrid(to_email: str, from_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Send email using SendGrid (placeholder - requires sendgrid library)."""
    try:
        # This would require: pip install sendgrid
        # import sendgrid
        # from sendgrid.helpers.mail import Mail
        
        logger.warning("SendGrid email service not implemented - install sendgrid library and implement this function")
        return False
    except Exception as e:
        logger.error(f"SendGrid email error: {e}")
        return False

async def send_email_smtp(to_email: str, from_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Send email using SMTP (placeholder - implement based on your SMTP settings)."""
    try:
        # This would use smtplib for SMTP sending
        logger.warning("SMTP email service not implemented - implement based on your SMTP provider")
        return False
    except Exception as e:
        logger.error(f"SMTP email error: {e}")
        return False 