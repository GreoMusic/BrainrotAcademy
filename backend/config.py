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
REALTIME_STT_MODEL = os.getenv(
    "REALTIME_STT_MODEL", "voxtral-mini-transcribe-realtime-2602"
)

DATA_DIR = BASE_DIR / "data"
TOPICS_DIR = DATA_DIR / "topics"
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = STATIC_DIR / "audio"
CLIPS_DIR = STATIC_DIR / "clips"

# Current Mistral preset voice IDs. The podcast uses restrained American
# deliveries so it sounds conversational rather than theatrical. All remain
# overridable from backend/.env.
VOICE_HOST_A = os.getenv("VOICE_HOST_A", "c69964a6-ab8b-4f8a-9465-ec0925096ec8")  # Paul - Neutral
VOICE_HOST_B = os.getenv("VOICE_HOST_B", "01d985cd-5e0c-4457-bfd8-80ba31a5bc03")  # Paul - Cheerful
VOICE_COACH = os.getenv("VOICE_COACH", "01d985cd-5e0c-4457-bfd8-80ba31a5bc03")   # Paul - Cheerful

# Transition engine tuning.
LEARN_CARDS_PER_ROUND = 3
QUIZ_CARDS_PER_CHECK = 3
PASS_THRESHOLD = 0.7
SCROLL_BUDGET = 8
