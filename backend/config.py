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
# NB: the docs' `voxtral-mini-transcribe-*` ids are not served on this account.
# The general audio model handles the transcriptions endpoint; verified by
# round-tripping our own TTS output back through it in tools/smoke_test.py.
STT_MODEL = os.getenv("STT_MODEL", "voxtral-mini-latest")

DATA_DIR = BASE_DIR / "data"
TOPICS_DIR = DATA_DIR / "topics"
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = STATIC_DIR / "audio"
CLIPS_DIR = STATIC_DIR / "clips"

# Preset voices, from audio.voices.list(type_="preset").
#
# They ship as <family>_<emotion> slugs, so a host is a voice FAMILY and each
# line picks an emotion from it. That is what stops a two-hander sounding like
# one narrator reading both parts: the skeptic can be confused, then sarcastic,
# then curious. The slug and the uuid are interchangeable as a voice_id; slugs
# are used here because they compose with the emotion.
#
# Casting follows main's choice of Jane + Oliver. The skeptic has to be Jane -
# Oliver's family carries no `confused` or `sarcasm`, which are exactly the
# registers that role needs.
VOICE_HOST_A = os.getenv("VOICE_HOST_A", "gb_oliver")  # the explainer
VOICE_HOST_B = os.getenv("VOICE_HOST_B", "gb_jane")    # the skeptic
VOICE_COACH = os.getenv("VOICE_COACH", "gb_jane_confident")

# Each family carries a different emotion set; asking for one it lacks 404s.
VOICE_EMOTIONS = {
    "en_paul": {"neutral", "happy", "sad", "frustrated", "excited",
                "confident", "cheerful", "angry"},
    "gb_jane": {"neutral", "curious", "confused", "sarcasm", "confident",
                "frustrated", "sad", "jealousy", "shameful"},
    "gb_oliver": {"neutral", "curious", "excited", "confident", "cheerful",
                  "sad", "angry"},
}
DEFAULT_EMOTION = "neutral"

# Transition engine tuning.
LEARN_CARDS_PER_ROUND = 3
PASS_THRESHOLD = 0.7
SCROLL_BUDGET = 6
