"""Conversational coach - the "checked learning" flow.

Unlike the feed, this route is live: it calls Mistral on every turn. That is
deliberate, because it is the one place a judge sees the model actually
reacting to them. Everything here degrades to text if audio is unavailable.
"""
from __future__ import annotations

import base64
import json
import queue
import re
import threading
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

import config
import content
import mistral_client as mc

bp = Blueprint("coach", __name__, url_prefix="/api/coach")

# How many exchanges before the coach is asked to render a verdict.
TURNS_BEFORE_VERDICT = 3


def _coach_payload(user_text: str, topic: str, history: list[dict]) -> dict:
    try:
        pack = content.load_pack(topic)
        system = pack.get("coach_system", "You are a tutor.")
    except content.TopicNotFound:
        system = "You are a warm, sharp tutor. Keep replies under 40 words."

    turns_taken = sum(1 for m in history if m.get("role") == "user") + 1
    closing = turns_taken >= TURNS_BEFORE_VERDICT
    system += (
        "\n\nReply as JSON: {\"reply\":str,\"understood\":bool,\"done\":bool}. "
        "'understood' is whether their LAST answer showed real understanding. "
        "'done' is true only when you have enough evidence to judge them. "
        "The reply will be spoken aloud: use one or two short, warm, conversational "
        "sentences with natural contractions and punctuation. Never use markdown, "
        "lists, labels, or stage directions."
    )
    if closing:
        system += " You have asked enough - set done to true this turn."

    convo = "\n".join(
        "{}: {}".format(m.get("role", "user"), m.get("content", ""))
        for m in history[-6:]
    )
    prompt = "{}\n\nuser: {}".format(convo, user_text) if convo else user_text
    out = mc.chat_json(prompt, system=system, temperature=0.6)
    return {
        "transcript": user_text,
        "reply": (out.get("reply") or "").strip() or "Tell me more.",
        "understood": bool(out.get("understood")),
        "done": bool(out.get("done")) or closing,
    }


@bp.post("/turn")
def turn():
    """One exchange. Accepts text or audio, always answers with text (+ audio).

    Multipart when the user spoke:  audio=<blob>, topic=..., history=<json>
    JSON when the user typed:       {"text":..., "topic":..., "history":[...]}
    """
    import json as _json

    if request.files.get("audio"):
        blob = request.files["audio"].read()
        topic = request.form.get("topic", "")
        history = _json.loads(request.form.get("history") or "[]")
        want_audio = request.form.get("audio_reply", "1") != "0"
        try:
            user_text = mc.transcribe(blob, filename="turn.webm")
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": "transcription failed: {}".format(exc)}), 502
    else:
        body = request.get_json(silent=True) or {}
        user_text = (body.get("text") or "").strip()
        topic = body.get("topic", "")
        history = body.get("history") or []
        want_audio = bool(body.get("audio_reply"))

    if not user_text:
        return jsonify({"error": "nothing said"}), 400

    try:
        payload = _coach_payload(user_text, topic, history)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502

    if want_audio:
        try:
            payload["audio"] = "data:audio/mp3;base64," + base64.b64encode(
                mc.tts(payload["reply"], voice_id=config.VOICE_COACH)
            ).decode()
        except Exception as exc:  # noqa: BLE001
            # A missing voice must not cost the user their answer.
            payload["audio_error"] = str(exc)

    return jsonify(payload)


@bp.post("/turn/stream")
def turn_stream():
    """Stream reply words and Voxtral PCM together as newline-delimited JSON."""
    body = request.get_json(silent=True) or {}
    user_text = (body.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "nothing said"}), 400

    try:
        payload = _coach_payload(user_text, body.get("topic", ""), body.get("history") or [])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502

    def event(kind: str, **data) -> str:
        return json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n"

    @stream_with_context
    def generate():
        audio_events: queue.Queue[tuple[str, object]] = queue.Queue()

        def synthesize() -> None:
            sent_audio = False
            try:
                for attempt in range(2):
                    try:
                        for chunk in mc.tts_stream(payload["reply"], voice_id=config.VOICE_COACH):
                            sent_audio = True
                            audio_events.put(("audio", base64.b64encode(chunk).decode()))
                        break
                    except Exception as exc:  # noqa: BLE001
                        # Retry once only when the stream failed before producing
                        # audio. Retrying mid-utterance would repeat spoken words.
                        if attempt == 0 and not sent_audio:
                            continue
                        audio_events.put(("audio_error", str(exc)))
                        break
            finally:
                audio_events.put(("audio_done", None))

        threading.Thread(target=synthesize, daemon=True).start()
        yield event("start", transcript=user_text, sample_rate=24000)

        # Voxtral starts producing PCM while these reply words are revealed.
        # If synthesis is slower than a very short reply, hold only its final
        # word until the first audio delta instead of letting text finish first.
        words = re.findall(r"\S+\s*", payload["reply"])
        audio_started = False
        audio_finished = False
        for index, word in enumerate(words):
            if index == len(words) - 1 and not audio_started and not audio_finished:
                while not audio_started:
                    kind, value = audio_events.get()
                    yield event(kind, **({"audio": value} if kind == "audio" else {"error": value} if value else {}))
                    audio_started = kind == "audio"
                    audio_finished = kind == "audio_done"
                    if kind in {"audio_error", "audio_done"}:
                        break
                if audio_started:
                    time.sleep(0.12)

            yield event("text_delta", text=word)
            while True:
                try:
                    kind, value = audio_events.get_nowait()
                except queue.Empty:
                    break
                yield event(kind, **({"audio": value} if kind == "audio" else {"error": value} if value else {}))
                audio_started = audio_started or kind == "audio"
                audio_finished = audio_finished or kind == "audio_done"
            time.sleep(0.045)

        audio_done = audio_finished
        while not audio_done:
            kind, value = audio_events.get()
            audio_done = kind == "audio_done"
            yield event(kind, **({"audio": value} if kind == "audio" else {"error": value} if value else {}))

        yield event(
            "result",
            understood=payload["understood"],
            done=payload["done"],
        )

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/grade")
def grade():
    """Grade a free-text answer against an expected one."""
    body = request.get_json(silent=True) or {}
    answer = (body.get("answer") or "").strip()
    expected = body.get("expected") or ""
    if not answer:
        return jsonify({"error": "answer required"}), 400

    try:
        out = mc.chat_json(
            "Question: {}\nExpected: {}\nStudent said: {}\n\n"
            'Return {{"correct":bool,"feedback":str}} - feedback under 25 words, '
            "and be generous about wording but strict about the actual idea.".format(
                body.get("question", ""), expected, answer
            ),
            system="You grade short answers fairly. Output JSON only.",
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502

    return jsonify({"correct": bool(out.get("correct")), "feedback": out.get("feedback", "")})
