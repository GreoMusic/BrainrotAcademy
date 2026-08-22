"""Central config. Model ids live here so a deprecation is a one-line fix."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# Verified Aug 2026. See plan for the capability -> model mapping.
CHAT_MODEL = os.getenv("CHAT_MODEL", "mistral-medium-latest")
TTS_MODEL = os.getenv("TTS_MODEL", "voxtral-mini-tts-latest")
STT_MODEL = os.getenv("STT_MODEL", "voxtral-mini-transcribe-latest")

DATA_DIR = BASE_DIR / "data"
TOPICS_DIR = DATA_DIR / "topics"
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = STATIC_DIR / "audio"
CLIPS_DIR = STATIC_DIR / "clips"

# Two distinct preset voices is what makes it read as a podcast and not as
# a text-to-speech reading. Overridable once we know the real preset names.
VOICE_HOST_A = os.getenv("VOICE_HOST_A", "Ana")
VOICE_HOST_B = os.getenv("VOICE_HOST_B", "Rick")
VOICE_COACH = os.getenv("VOICE_COACH", "Ana")

# Transition engine tuning.
LEARN_CARDS_PER_ROUND = 3
PASS_THRESHOLD = 0.7
SCROLL_BUDGET = 6
