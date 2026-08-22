"""WebSocket proxy for Voxtral Realtime transcription.

The browser streams raw PCM here instead of connecting to Mistral directly,
so the API key never leaves the backend. Transcript deltas are forwarded to
the coach card as soon as Voxtral emits them.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import Any

from flask_sock import Sock
from mistralai.client import Mistral
from mistralai.client.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

import config

sock = Sock()
_END = object()
_SUPPORTED_SAMPLE_RATES = {8000, 16000, 22050, 44100, 48000}


def _send(ws: Any, payload: dict[str, Any]) -> None:
    """Best-effort send; the user may close the card while a delta is in flight."""
    try:
        ws.send(json.dumps(payload))
    except Exception:  # noqa: BLE001
        pass


def _finish_queue(chunks: queue.Queue[bytes | object]) -> None:
    """Unblock the transcription task even if a disconnected client filled the queue."""
    try:
        chunks.put_nowait(_END)
    except queue.Full:
        try:
            chunks.get_nowait()
        except queue.Empty:
            pass
        chunks.put_nowait(_END)


def _receive_audio(ws: Any, chunks: queue.Queue[bytes | object]) -> None:
    try:
        while True:
            message = ws.receive()
            if message is None:
                break
            if isinstance(message, bytes):
                chunks.put(message)
                continue
            try:
                event = json.loads(message)
            except (TypeError, json.JSONDecodeError):
                continue
            if event.get("type") == "stop":
                break
    finally:
        _finish_queue(chunks)


async def _transcribe(ws: Any, chunks: queue.Queue[bytes | object], sample_rate: int) -> None:
    async def audio_stream():
        while True:
            chunk = await asyncio.to_thread(chunks.get)
            if chunk is _END:
                break
            yield chunk

    client = Mistral(api_key=config.MISTRAL_API_KEY)
    full_text: list[str] = []
    audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=sample_rate)

    async for event in client.audio.realtime.transcribe_stream(
        audio_stream=audio_stream(),
        model=config.REALTIME_STT_MODEL,
        audio_format=audio_format,
        target_streaming_delay_ms=480,
    ):
        if isinstance(event, RealtimeTranscriptionSessionCreated):
            _send(ws, {"type": "ready"})
        elif isinstance(event, TranscriptionStreamTextDelta):
            full_text.append(event.text)
            _send(ws, {"type": "delta", "text": event.text})
        elif isinstance(event, TranscriptionStreamDone):
            _send(ws, {"type": "done", "text": "".join(full_text).strip()})
            break
        elif isinstance(event, RealtimeTranscriptionError):
            _send(ws, {"type": "error", "error": str(event.error)})
            break


@sock.route("/api/coach/realtime")
def coach_realtime(ws: Any) -> None:
    if not config.MISTRAL_API_KEY:
        _send(ws, {"type": "error", "error": "MISTRAL_API_KEY is not configured"})
        return

    try:
        start = json.loads(ws.receive(timeout=5) or "{}")
        sample_rate = int(start.get("sample_rate", 16000))
    except (TypeError, ValueError, json.JSONDecodeError):
        _send(ws, {"type": "error", "error": "invalid start message"})
        return

    if start.get("type") != "start" or sample_rate not in _SUPPORTED_SAMPLE_RATES:
        _send(ws, {"type": "error", "error": "unsupported audio format"})
        return

    chunks: queue.Queue[bytes | object] = queue.Queue(maxsize=128)
    receiver = threading.Thread(target=_receive_audio, args=(ws, chunks), daemon=True)
    receiver.start()

    try:
        asyncio.run(_transcribe(ws, chunks, sample_rate))
    except Exception as exc:  # noqa: BLE001
        _send(ws, {"type": "error", "error": str(exc)})
    finally:
        _finish_queue(chunks)
