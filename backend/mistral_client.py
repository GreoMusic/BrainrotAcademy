"""Thin wrapper over the Mistral SDK.

Everything the app does with Mistral goes through here so that model ids,
retries, and response unwrapping live in exactly one place.

SDK surface verified against mistralai 2.9.4:
  - import path is `mistralai.client`, not `mistralai`
  - audio.speech.complete(...) -> SpeechResponse(audio_data=<base64 str>)
  - audio.transcriptions.complete(...) -> TranscriptionResponse(text=...)
  - audio.voices.list(type_="preset") enumerates the built-in voices
"""
from __future__ import annotations

import base64
import json
import re
import time
from functools import lru_cache
from typing import Any

import config

_RETRIES = 2
_BACKOFF = 1.5


@lru_cache(maxsize=1)
def get_client():
    from mistralai.client import Mistral

    if not config.MISTRAL_API_KEY:
        raise RuntimeError(
            "MISTRAL_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and put your key in it."
        )
    return Mistral(api_key=config.MISTRAL_API_KEY)


def _retry(fn, *, what: str):
    """One shared retry policy. Hackathon wifi is not reliable."""
    last = None
    for attempt in range(_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - surface anything, but retry first
            last = exc
            if attempt < _RETRIES:
                time.sleep(_BACKOFF * (attempt + 1))
    raise RuntimeError(f"mistral {what} failed after {_RETRIES + 1} tries: {last}")


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------
def chat_text(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    temperature: float = 0.7,
    model: str | None = None,
) -> str:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.extend(history or [])
    messages.append({"role": "user", "content": prompt})

    def call():
        return get_client().chat.complete(
            model=model or config.CHAT_MODEL,
            messages=messages,
            temperature=temperature,
        )

    resp = _retry(call, what="chat")
    return (resp.choices[0].message.content or "").strip()


def _extract_json(raw: str) -> dict[str, Any]:
    """Models occasionally wrap JSON in prose or fences. Salvage it."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    span = re.search(r"[{\[].*[}\]]", raw, re.S)
    if span:
        return json.loads(span.group(0))
    raise ValueError(f"no JSON found in model output: {raw[:200]!r}")


def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    model: str | None = None,
) -> dict[str, Any]:
    """Chat constrained to a JSON object, with salvage on malformed output."""
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def call():
        return get_client().chat.complete(
            model=model or config.CHAT_MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

    resp = _retry(call, what="chat_json")
    return _extract_json(resp.choices[0].message.content or "")


def vision_json(image_bytes: bytes, prompt: str, *, mime: str = "image/jpeg") -> dict[str, Any]:
    """Ask the model a structured question about an image (touch-grass judge)."""
    b64 = base64.b64encode(image_bytes).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
            ],
        }
    ]

    def call():
        return get_client().chat.complete(
            model=config.CHAT_MODEL,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    resp = _retry(call, what="vision")
    return _extract_json(resp.choices[0].message.content or "")


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------
def tts(text: str, *, voice_id: str, fmt: str = "mp3") -> bytes:
    """Text -> speech bytes. `audio_data` comes back base64-encoded."""

    def call():
        return get_client().audio.speech.complete(
            model=config.TTS_MODEL,
            input=text,
            voice_id=voice_id,
            response_format=fmt,
        )

    resp = _retry(call, what="tts")
    return base64.b64decode(resp.audio_data)


def transcribe(audio_bytes: bytes, *, filename: str = "clip.webm", language: str | None = None) -> str:
    def call():
        return get_client().audio.transcriptions.complete(
            model=config.STT_MODEL,
            file={"file_name": filename, "content": audio_bytes},
            **({"language": language} if language else {}),
        )

    resp = _retry(call, what="transcribe")
    return (resp.text or "").strip()


def list_preset_voices() -> list[dict[str, Any]]:
    """Discover real preset voice ids rather than hardcoding guesses."""
    resp = _retry(lambda: get_client().audio.voices.list(type_="preset", limit=50), what="voices.list")
    out = []
    for v in getattr(resp, "voices", None) or getattr(resp, "data", None) or []:
        out.append(
            {
                "id": getattr(v, "id", None) or getattr(v, "voice_id", None),
                "name": getattr(v, "name", None),
                "gender": getattr(v, "gender", None),
                "languages": getattr(v, "languages", None),
            }
        )
    return out
