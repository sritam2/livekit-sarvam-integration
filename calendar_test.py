#!/usr/bin/env python3
"""
Google Calendar Functions Test File
Test each calendar function individually before integrating into the agent.
"""

import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv(".env")

def get_calendar_service():
    """Initialize Google Calendar service using service account credentials."""
    try:
        # Path to your service account key file
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        if not service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE not found in environment")
        
        print(f"Using service account file: {service_account_file}")
        
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, 
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=credentials)
        print("✅ Calendar service initialized successfully!")
        
        # Show service account email
        print(f"🔑 Service account email: {credentials.service_account_email}")
        
        return service
    except Exception as e:
        print(f"❌ Error initializing calendar service: {e}")
        return None

def test_calendar_connection():
    """Test if we can connect to Google Calendar API."""
    print("🔧 Testing Calendar Connection...")
    service = get_calendar_service()
    
    if service is None:
        return False
    
    try:
        # Try to list calendars to test connection
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        print(f"✅ Connected! Found {len(calendars)} calendars:")
        for calendar in calendars:
            print(f"  - {calendar['summary']} (ID: {calendar['id']})")
        
        return True
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def list_upcoming_events(days_ahead=7):
    """List upcoming calendar events."""
    print(f"\n📅 Listing upcoming events for next {days_ahead} days...")
    
    service = get_calendar_service()
    if not service:
        return None
    
    try:
        # Calculate time range
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        future = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat().replace('+00:00', 'Z')
        
        print(f"Time range: {now} to {future}")
        
        # Get events
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        print(f"Using calendar ID: {calendar_id}")
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            timeMax=future,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            print("📭 No upcoming events found.")
            return []
        
        print(f"✅ Found {len(events)} upcoming events:")
        event_list = []
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'No title')
            
            if 'T' in start:  # DateTime format
                event_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = event_time.strftime('%B %d at %I:%M %p')
            else:  # Date only
                event_time = datetime.strptime(start, '%Y-%m-%d')
                formatted_time = event_time.strftime('%B %d (All day)')
            
            event_info = f"'{title}' on {formatted_time}"
            event_list.append(event_info)
            print(f"  {i}. {event_info}")
        
        return event_list
        
    except Exception as e:
        print(f"❌ Error listing events: {e}")
        return None

def add_calendar_event(title, date, start_time, duration_minutes=60, description=""):
    """Add a new calendar event."""
    print(f"\n📝 Adding calendar event: '{title}' on {date} at {start_time}")
    
    service = get_calendar_service()
    if not service:
        return None
    
    try:
        # Parse start and end times
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        print(f"Event time: {start_datetime} to {end_datetime} (Duration: {duration_minutes} min)")
        
        # Create event
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        print(f"Using calendar ID: {calendar_id}")
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        print(f"✅ Successfully created event!")
        print(f"   Event ID: {created_event['id']}")
        print(f"   Event URL: {created_event.get('htmlLink', 'N/A')}")
        
        return created_event
        
    except Exception as e:
        print(f"❌ Error adding calendar event: {e}")
        return None

def main():
    """Main test function - run all tests."""
    print("🚀 Starting Google Calendar Function Tests")
    print("=" * 50)
    
    # Test 1: Connection
    if not test_calendar_connection():
        print("\n❌ Calendar connection failed. Please check your setup:")
        print("1. GOOGLE_SERVICE_ACCOUNT_FILE path in .env")
        print("2. Service account JSON file exists")
        print("3. Calendar API is enabled")
        print("4. Calendar is shared with service account")
        return
    
    print("\n" + "=" * 50)
    
    # Test 2: List upcoming events
    events = list_upcoming_events()
    
    print("\n" + "=" * 50)
    
    # Test 3: Add a new event
    test_event = add_calendar_event(
        title="LiveKit Agent Test Meeting",
        date="2025-08-01",  # Tomorrow (adjust as needed)
        start_time="15:30",  # 3:30 PM
        duration_minutes=30,
        description="Test event created by LiveKit calendar agent"
    )
    
    if test_event:
        print("\n🎉 Event creation test passed!")
        
        # Verify by listing events again
        print("\n📅 Listing events again to verify:")
        list_upcoming_events(days_ahead=3)
    
    print("\n" + "=" * 50)
    print("✅ Tests completed!")
    print("\n📋 Functions tested:")
    print("  ✅ Connection test")
    print("  ✅ List upcoming events") 
    print("  ✅ Add calendar event")
    print("\n🚀 Next: Add availability checking and free slots functions!")

if __name__ == "__main__":
    main()