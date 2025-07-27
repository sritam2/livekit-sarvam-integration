from dotenv import load_dotenv
import os
from typing import AsyncIterable
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    openai,
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
    sarvam
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")

async def entrypoint(ctx: agents.JobContext):
    # code to print the values of .env globals
    print("Agent connecting to livekit cloud server. Agent session will be started soon.")

    #session = AgentSession(
    #    stt=deepgram.STT(model="nova-3", language="multi"),
    #    llm=openai.LLM(model="gpt-4o-mini"),
    #    tts=cartesia.TTS(model="sonic-2", voice="f786b574-daa5-4673-aa0c-cbe3e8534c02"),
    #    vad=silero.VAD.load(),
    #    turn_detection=MultilingualModel(),
    #)

    session = AgentSession(
        stt=sarvam.STT(language="en-IN", model="saaras:v2.5",
                       api_key=os.getenv("SARVAM_API_KEY"),
                       base_url='https://api.sarvam.ai/speech-to-text-translate'),

        llm=openai.LLM(model="gpt-4o-mini"),
        tts = sarvam.TTS(
            target_language_code="en-IN",
            speaker="anushka",
            model="bulbul:v2",
            api_key=os.getenv("SARVAM_API_KEY"),
            base_url= 'https://api.sarvam.ai/text-to-speech',
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(), 
        ),
    )

    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))