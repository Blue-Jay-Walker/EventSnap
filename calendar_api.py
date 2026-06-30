from googleapiclient.discovery import build
import json
from datetime import datetime

CALENDAR_SUMMARY = "Events to Decide"

def get_calendar_service(credentials):
    """Builds and returns the Google Calendar API service."""
    return build('calendar', 'v3', credentials=credentials)

def get_or_create_calendar(service, calendar_summary=CALENDAR_SUMMARY):
    """Finds the calendar by summary, creates it if not found, and returns its ID."""
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == calendar_summary:
                return calendar_list_entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
            
    # If we get here, the calendar doesn't exist. Create it.
    calendar = {
        'summary': calendar_summary,
        'timeZone': 'Europe/Zurich'
    }
    created_calendar = service.calendars().insert(body=calendar).execute()
    return created_calendar['id']

def add_event_to_calendar(service, calendar_id: str, event_details):
    """Adds the extracted event to the specified calendar."""
    import urllib.parse
    
    description_text = f"{event_details.description}\n\nCategory: {event_details.category}\nPrice: {event_details.price}\n\nSource: {event_details.source_url or 'Manual Text Input'}"
    
    if event_details.location and event_details.location.lower() != 'online':
        encoded_location = urllib.parse.quote(event_details.location)
        maps_link = f"https://www.google.com/maps/search/?api=1&query={encoded_location}"
        description_text += f"\n\nGoogle Maps: {maps_link}"

    event_body = {
        'summary': event_details.title,
        'description': description_text,
        'status': 'tentative',
    }
    
    if event_details.location:
        event_body['location'] = event_details.location

    from datetime import timedelta
    from zoneinfo import ZoneInfo
    
    # Determine start date (default to today if missing)
    start_date = event_details.start_date
    if not start_date:
        zurich_tz = ZoneInfo("Europe/Zurich")
        start_date = datetime.now(zurich_tz).strftime("%Y-%m-%d")
        
    start_time = event_details.start_time
    
    # Build start datetime if start_time is present
    if start_time:
        try:
            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            start_dt = None
    else:
        start_dt = None

    # Handle end date/time
    end_date = event_details.end_date or start_date
    end_time = event_details.end_time
    
    if start_dt:
        if end_time:
            try:
                end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                end_dt = start_dt + timedelta(hours=2)
        else:
            # Default to 2 hours after start time if end time is not specified
            end_dt = start_dt + timedelta(hours=2)
            
        event_body['start'] = {
            'dateTime': start_dt.strftime("%Y-%m-%dT%H:%M:00"),
            'timeZone': 'Europe/Zurich'
        }
        event_body['end'] = {
            'dateTime': end_dt.strftime("%Y-%m-%dT%H:%M:00"),
            'timeZone': 'Europe/Zurich'
        }
    else:
        # All-day event
        event_body['start'] = {'date': start_date}
        event_body['end'] = {'date': end_date}
        
    created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    return created_event.get('htmlLink')
