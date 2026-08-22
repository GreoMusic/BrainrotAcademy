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
STT_MODEL = os.getenv("STT_MODEL", "voxtral-mini-latest")

DATA_DIR = BASE_DIR / "data"
TOPICS_DIR = DATA_DIR / "topics"
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = STATIC_DIR / "audio"
CLIPS_DIR = STATIC_DIR / "clips"

# Current Mistral preset voice IDs. Keep two distinct voices so podcast turns
# read as a conversation. All remain overridable from backend/.env.
VOICE_HOST_A = os.getenv("VOICE_HOST_A", "5de47977-6e47-4266-a938-3bc1d76b4676")  # Jane - Curious
VOICE_HOST_B = os.getenv("VOICE_HOST_B", "390c8a2b-60a6-4882-8437-c49a8bd33b63")  # Oliver - Curious
VOICE_COACH = os.getenv("VOICE_COACH", "cbe96cf0-85ec-4a10-accb-0b35c93b6dfd")   # Jane - Confident

# Transition engine tuning.
LEARN_CARDS_PER_ROUND = 3
PASS_THRESHOLD = 0.7
SCROLL_BUDGET = 6
