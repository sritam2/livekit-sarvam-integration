import logging
import os
import pickle
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RoomOutputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins import sarvam

import requests
from datetime import datetime

logger = logging.getLogger("agent")

load_dotenv(".env")

class Assistant(Agent):
    def __init__(self, current_datetime: str = None) -> None:
        # Get current date/time if not provided
        if current_datetime is None:
            now = datetime.now()
            current_datetime = now.strftime("%A, %B %d, %Y at %I:%M %p")
            current_date = now.strftime("%Y-%m-%d")
        else:
            # Parse provided datetime for date extraction
            current_date = current_datetime.split()[0] if current_datetime else "2025-07-31"
        
        super().__init__(
            instructions = f"""You are a polite and professional voice AI receptionist for an oxygen therapy clinic named PREETU OXYGEN THERAPY CLINIC. 
            When your session starts, you start the conversation by saying "Namaskar, this is Lavanya from Preetu Oxygen Therapy Clinic. How can I help you today?"
            
            **CURRENT DATE & TIME CONTEXT:**
            - Today is: {current_datetime}
            - Use this date format for appointments: YYYY-MM-DD (e.g., {current_date})
            - When customers say "tomorrow", "next week", "5th of August", etc., calculate from today's date
            - Always use the correct year (2025) for current and future appointments
            
            Your **only purpose** is to manage appointment requests over the phone, including:
            1. Checking availability
            2. Booking new appointments
            3. Listing upcoming appointments

            You **must not** answer any questions outside this scope. 
            If a caller asks irrelevant questions (e.g., about the weather, news, or general knowledge), respond politely:
                "I’m sorry, I can only help with booking and managing appointments for our clinic."

            ### Personality & Style
            - Friendly, calm, professional
            - Keep responses **short and conversational**, 1–2 sentences
            - Ask **one question at a time**
            - Confirm details before booking
            - Do **not** provide medical advice

            ### Tools you can use:
            1. get_current_datetime() - Get fresh current date/time if needed for calculations
            2. list_upcoming_events(days_ahead: int = 7, customer_id: str = "default")
                - Use to list existing appointments for a caller within the given number of days.
            3. add_calendar_event(title: str, date: str, start_time: str, duration_minutes: int = 60, description: str = "", customer_id: str = "default")
                - Use to book a new appointment once details are confirmed.
            4. check_availability(date: str, start_time: str, end_time: str, customer_id: str = "default")
                - Use to check if a slot is free before confirming a booking.

            ### Behavior Rules
            - **Do not make up information** or offer times without checking availability.
            - **Politely reject all off-topic queries**.
            - Always **confirm** the date, time, and service with the caller before booking.
            - After booking, **summarize the appointment clearly**.
            - If a tool call fails, apologize and ask the caller to try again or offer to have a human follow up.

            Example off-topic response:
                Caller: "What is the capital of India?"
                Agent: "I’m here only to help with appointment bookings. Would you like to check available slots?"

            Example booking flow:
            1. Greet the caller and ask their intent
            2. Collect service type, date, and preferred time
            3. Use check_availability to confirm free slots
            4. Offer the nearest available times
            5. On confirmation, call add_calendar_event
            6. Confirm and summarize the booking

            Stick strictly to this purpose. Do not engage in unrelated conversation.
            """,
        )

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        """Use this tool to look up current weather information in the given location.

        If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.

        Args:
            location: The location to look up weather information for (e.g. city name)
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."
    
    @function_tool
    async def lookup_time(self, context: RunContext, city: str):
        """Use this tool to look up current time information in the given city.

        If the location is not supported by the time service, the tool will indicate this. You must tell the user the location's time is unavailable.

        Args:
            city: The city to look up time information for (e.g. city name)
        """

        logger.info(f"Looking up time for {city}")

        return "the time is 10:07 AM."

    @function_tool
    async def get_current_datetime(self, context: RunContext):
        """Get the current date and time. Use this if you need to know the exact current time during the conversation.
        
        This is helpful for calculating relative dates like 'tomorrow', 'next week', etc.
        """
        now = datetime.now()
        current_datetime = now.strftime("%A, %B %d, %Y at %I:%M %p")
        logger.info(f"Current datetime requested: {current_datetime}")
        return f"The current date and time is {current_datetime}"

    def _get_oauth_credentials(self, customer_id="default"):
        """Get OAuth 2.0 credentials for calendar access."""
        try:
            creds = None
            token_file = f"token_{customer_id}.pickle"
            
            # Load existing credentials
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)
            
            # If credentials are invalid or don't exist, they need to be set up
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired OAuth credentials...")
                    try:
                        creds.refresh(Request())
                        logger.info("OAuth credentials refreshed successfully!")
                    except Exception as e:
                        logger.error(f"Failed to refresh credentials: {e}")
                        return None
                else:
                    logger.warning("No valid OAuth credentials found. Customer needs to authorize first.")
                    return None
            
            return creds
        except Exception as e:
            logger.error(f"Error getting OAuth credentials: {e}")
            return None

    def _get_calendar_service(self, customer_id="default"):
        """Get Google Calendar service using OAuth credentials."""
        try:
            credentials = self._get_oauth_credentials(customer_id)
            if not credentials:
                return None
            
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            logger.error(f"Error initializing calendar service: {e}")
            return None

    @function_tool
    async def list_upcoming_events(self, context: RunContext, days_ahead: int = 7, customer_id: str = "default"):
        """List upcoming calendar events for the next few days.

        Args:
            days_ahead: Number of days ahead to look for events (default: 7)
            customer_id: Customer identifier for OAuth tokens (default: "default")
        """
        logger.info(f"Listing upcoming events for {days_ahead} days")
        
        try:
            service = self._get_calendar_service(customer_id)
            if not service:
                return "Sorry, I can't access your calendar right now. You may need to authorize calendar access first."

            # Calculate time range
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            future = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat().replace('+00:00', 'Z')
            
            # Get events from primary calendar
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=future,
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return f"You have no upcoming events in the next {days_ahead} days."
            
            # Format events for voice response
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                title = event.get('summary', 'No title')
                
                if 'T' in start:  # DateTime format
                    event_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_time = event_time.strftime('%B %d at %I:%M %p')
                else:  # Date only
                    event_time = datetime.strptime(start, '%Y-%m-%d')
                    formatted_time = event_time.strftime('%B %d')
                
                event_list.append(f"{title} on {formatted_time}")
            
            if len(event_list) == 1:
                return f"You have 1 upcoming event: {event_list[0]}"
            else:
                events_text = ", ".join(event_list)
                return f"You have {len(event_list)} upcoming events: {events_text}"
                
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            return "Sorry, I had trouble accessing your calendar events."

    @function_tool
    async def add_calendar_event(self, context: RunContext, title: str, date: str, start_time: str, duration_minutes: int = 60, description: str = "", customer_id: str = "default"):
        """Add a new event to the calendar.

        Args:
            title: Title of the event
            date: Date of the event (format: YYYY-MM-DD, e.g., 2025-08-01)
            start_time: Start time in 24-hour format (e.g., 14:30 for 2:30 PM)
            duration_minutes: Duration in minutes (default: 60)
            description: Optional description of the event
            customer_id: Customer identifier for OAuth tokens (default: "default")
        """
        logger.info(f"Adding calendar event: {title} on {date} at {start_time}")
        
        try:
            service = self._get_calendar_service(customer_id)
            if not service:
                return "Sorry, I can't access your calendar to add the event. You may need to authorize calendar access first."

            # Parse start and end times
            start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
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
            
            created_event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Format response for voice
            formatted_start_time = start_datetime.strftime('%I:%M %p')
            formatted_date = start_datetime.strftime('%B %d')
            
            return f"Successfully added '{title}' to your calendar on {formatted_date} at {formatted_start_time} for {duration_minutes} minutes."
            
        except Exception as e:
            logger.error(f"Error adding calendar event: {e}")
            return f"Sorry, I couldn't add the event '{title}' to your calendar."

    @function_tool
    async def check_availability(self, context: RunContext, date: str, start_time: str, end_time: str, customer_id: str = "default"):
        """Check if you're available during a specific time period.

        Args:
            date: The date to check (format: YYYY-MM-DD, e.g., 2025-08-01)
            start_time: Start time in 24-hour format (e.g., 14:00 for 2 PM)
            end_time: End time in 24-hour format (e.g., 16:00 for 4 PM)
            customer_id: Customer identifier for OAuth tokens (default: "default")
        """
        logger.info(f"Checking availability on {date} from {start_time} to {end_time}")
        
        try:
            service = self._get_calendar_service(customer_id)
            if not service:
                return "Sorry, I can't access your calendar to check availability. You may need to authorize calendar access first."

            # Parse times
            start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M").isoformat() + 'Z'
            end_datetime = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M").isoformat() + 'Z'
            
            # Check for conflicts using freebusy query
            freebusy = service.freebusy().query(
                body={
                    "timeMin": start_datetime,
                    "timeMax": end_datetime,
                    "items": [{"id": "primary"}]
                }
            ).execute()
            
            busy_times = freebusy['calendars']['primary'].get('busy', [])
            
            # Format response for voice
            formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime('%B %d')
            formatted_start = datetime.strptime(start_time, "%H:%M").strftime('%I:%M %p')
            formatted_end = datetime.strptime(end_time, "%H:%M").strftime('%I:%M %p')
            
            if not busy_times:
                return f"Good news! You're available on {formatted_date} from {formatted_start} to {formatted_end}."
            else:
                conflicts = []
                for busy in busy_times:
                    busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                    conflicts.append(f"{busy_start.strftime('%I:%M %p')} to {busy_end.strftime('%I:%M %p')}")
                
                conflict_text = " and ".join(conflicts)
                return f"Sorry, you have conflicts on {formatted_date} from {conflict_text}."
                
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return f"Sorry, I couldn't check your availability for {date}."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # any combination of STT, LLM, TTS, or realtime API can be used
        llm=openai.LLM(model="gpt-4o-mini"),
        #stt=deepgram.STT(model="nova-3", language="multi"),
        stt=sarvam.STT(language="en-IN", model="saaras:v2.5",
                       api_key=os.getenv("SARVAM_API_KEY"),
                       base_url='https://api.sarvam.ai/speech-to-text-translate'),
        tts=deepgram.TTS(
            model="aura-2-odysseus-en",
            encoding="linear16",
            sample_rate=24000,
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            base_url="https://api.deepgram.com/v1/speak"
        ),
        # use LiveKit's turn detection model
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
    )

    # To use the OpenAI Realtime API, use the following session setup instead:
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel()
    # )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),  # Fresh datetime injected automatically in __init__
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

    # join the room when agent is ready
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
