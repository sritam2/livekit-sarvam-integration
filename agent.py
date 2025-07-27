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
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins import sarvam
from sarvamai import SarvamAI

load_dotenv()

# Initialize Sarvam AI client for translation
sarvam_client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

async def translate_to_indic(english_text: str, target_language: str = "hi-IN") -> str:
    """Translate English text to target Indian language using Sarvam AI."""
    try:
        response = sarvam_client.text.translate(
            input=english_text,
            source_language_code="en-IN",
            target_language_code=target_language,
            mode="modern-colloquial",
            speaker_gender="Female"
        )
        print(f"Translated: {english_text} -> {response.translated_text}")
        return response.translated_text
    except Exception as e:
        print(f"Translation error: {e}; falling back to original text")
        return english_text


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")

    async def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings,
    ) -> AsyncIterable:
        """Override the TTS node to translate text before synthesis.

        The default TTS node accepts an async iterable of strings and
        yields audio frames.  We wrap the incoming text stream in a
        translation coroutine, then pass it to the parent implementation.

        Args:
            text: An async iterable over strings produced by the LLM.  Each
                element represents a chunk of text to synthesize.
            model_settings: Settings controlling the behaviour of TTS.

        Yields:
            Audio frames representing the synthesized speech.
        """

        async def translated_stream() -> AsyncIterable[str]:
            # Iterate over each text chunk from the LLM and translate it.
            async for segment in text:
                try:
                    translated = await translate_to_indic(segment, target_language="od-IN")
                except Exception as exc:
                    # If translation fails, fall back to the original text.
                    print(f"Translation error: {exc}; falling back to original text")
                    translated = segment
                yield translated

        # Delegate to the default TTS node using the translated text.
        async for frame in super().tts_node(
            translated_stream(),
            model_settings,
        ):
            yield frame


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
        #stt=deepgram.STT(model="nova-3", language="multi"),
        stt=sarvam.STT(language="od-IN", model="saaras:v2.5",
                       api_key=os.getenv("SARVAM_API_KEY"),
                       base_url='https://api.sarvam.ai/speech-to-text-translate'),

        llm=openai.LLM(model="gpt-4o-mini"),
        tts = sarvam.TTS(
            target_language_code="od-IN",
            speaker="anushka",
            model="bulbul:v2",
            api_key=os.getenv("SARVAM_API_KEY"),
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