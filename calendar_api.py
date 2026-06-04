from googleapiclient.discovery import build
import json
from datetime import datetime

CALENDAR_SUMMARY = "Events to Decide"

def get_calendar_service(credentials):
    """Builds and returns the Google Calendar API service."""
    return build('calendar', 'v3', credentials=credentials)

def get_or_create_calendar(service):
    """Finds 'Events to Decide' calendar, creates it if not found, and returns its ID."""
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == CALENDAR_SUMMARY:
                return calendar_list_entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
            
    # If we get here, the calendar doesn't exist. Create it.
    calendar = {
        'summary': CALENDAR_SUMMARY,
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

    # Handle dates/times
    if event_details.start_date:
        if event_details.start_time:
            # LLM guarantees HH:MM format, just append seconds
            time_str = f"{event_details.start_time}:00"
            start_str = f"{event_details.start_date}T{time_str}"
            event_body['start'] = {'dateTime': start_str, 'timeZone': 'Europe/Zurich'}
        else:
            event_body['start'] = {'date': event_details.start_date}
    else:
        # Fallback if entirely unknown: schedule for today as all-day event
        today_str = datetime.now().strftime("%Y-%m-%d")
        event_body['start'] = {'date': today_str}
        
    if event_details.end_date:
        if event_details.end_time:
            # LLM guarantees HH:MM format, just append seconds
            time_str = f"{event_details.end_time}:00"
            end_str = f"{event_details.end_date}T{time_str}"
            event_body['end'] = {'dateTime': end_str, 'timeZone': 'Europe/Zurich'}
        else:
            event_body['end'] = {'date': event_details.end_date}
    elif event_details.start_date:
        # If no end date, use start date/time
        event_body['end'] = event_body['start']
        
    created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    return created_event.get('htmlLink')
