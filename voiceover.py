"""
Text-to-speech module — generates voiceover MP3 files.
Supports OpenAI TTS (default) and ElevenLabs.
"""

import time
from pathlib import Path
from config import (
    TTS_PROVIDER, OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, OUTPUT_DIR,
    MAX_RETRIES, RETRY_DELAY_SECONDS
)
from modules.logger import get_logger, log_event

log = get_logger("voiceover")


def generate_voiceover(script: str, topic_id: str) -> Path:
    """
    Generate a voiceover audio file from script text.

    Returns: Path to the generated MP3 file.
    """
    output_path = OUTPUT_DIR / "voiceovers" / f"{topic_id}.mp3"

    if TTS_PROVIDER == "openai":
        return _openai_tts(script, output_path)
    elif TTS_PROVIDER == "elevenlabs":
        return _elevenlabs_tts(script, output_path)
    else:
        raise ValueError(f"Unknown TTS provider: {TTS_PROVIDER}")


def _openai_tts(script: str, output_path: Path) -> Path:
    """Generate voiceover using OpenAI TTS API."""
    from openai import OpenAI

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — cannot generate voiceover")

    client = OpenAI(api_key=OPENAI_API_KEY)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.audio.speech.create(
                model=OPENAI_TTS_MODEL,
                voice=OPENAI_TTS_VOICE,
                input=script,
                response_format="mp3",
            )
            response.stream_to_file(str(output_path))
            log.info(f"Voiceover generated: {output_path}")
            return output_path

        except Exception as e:
            log.warning(f"OpenAI TTS attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                raise


def _elevenlabs_tts(script: str, output_path: Path) -> Path:
    """Generate voiceover using ElevenLabs API."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    for attempt in range(MAX_RETRIES):
        try:
            audio_generator = client.text_to_speech.convert(
                voice_id=ELEVENLABS_VOICE_ID,
                text=script,
                model_id="eleven_monolingual_v1",
            )
            # Write audio chunks to file
            with open(output_path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)

            log.info(f"Voiceover generated (ElevenLabs): {output_path}")
            return output_path

        except Exception as e:
            log.warning(f"ElevenLabs TTS attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                raise


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using moviepy."""
    from moviepy import AudioFileClip
    clip = AudioFileClip(str(audio_path))
    duration = clip.duration
    clip.close()
    return duration
