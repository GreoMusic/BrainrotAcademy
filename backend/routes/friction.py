"""Friction gate verification.

These gates are nudges, not cops - a photo of grass on a screen will pass, and
that is fine. The point is to make continuing cost something.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

import mistral_client as mc
import orchestrator as orch

bp = Blueprint("friction", __name__, url_prefix="/api/friction")


@bp.get("/math")
def math():
    difficulty = int(request.args.get("difficulty", 0))
    return jsonify(orch.make_math_problem(difficulty))


@bp.post("/touch-grass")
def touch_grass():
    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "photo required"}), 400

    try:
        out = mc.vision_json(
            photo.read(),
            'Is this photo taken outdoors, showing real plants, sky, or nature? '
            'Return {"outdoors":bool,"what":str,"reason":str} - "what" names what '
            'you see in 5 words, "reason" is one friendly sentence addressed to '
            "the person, whether or not they passed.",
            mime=photo.mimetype or "image/jpeg",
        )
    except Exception as exc:  # noqa: BLE001
        # Never trap the user behind a broken judge.
        return jsonify({"pass": True, "reason": "Could not verify - letting you through."}), 200

    ok = bool(out.get("outdoors"))
    return jsonify(
        {
            "pass": ok,
            "what": out.get("what", ""),
            "reason": out.get("reason") or ("Nice. Go back in." if ok else "That is not outside."),
        }
    )


@bp.post("/talk")
def talk():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "audio required"}), 400
    topic = request.form.get("topic", "the topic")

    try:
        transcript = mc.transcribe(audio.read(), filename="talk.webm")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"pass": True, "reason": "Could not transcribe - letting you through."}), 200

    if len(transcript.split()) < 8:
        return jsonify(
            {
                "pass": False,
                "transcript": transcript,
                "reason": "That was too short to be a real conversation.",
            }
        )

    try:
        out = mc.chat_json(
            "Someone was asked to explain {} out loud to another person.\n"
            "Transcript: {}\n\n"
            'Return {{"real":bool,"reason":str}} - "real" is whether this sounds '
            "like a genuine spoken explanation of the topic (not gibberish, not "
            "reading a definition). Be lenient. 'reason' is one warm sentence "
            "addressed to them.".format(topic.replace("-", " "), transcript),
            system="You judge spoken explanations generously. Output JSON only.",
            temperature=0.3,
        )
    except Exception:  # noqa: BLE001
        return jsonify({"pass": True, "transcript": transcript, "reason": "Good enough."}), 200

    return jsonify(
        {
            "pass": bool(out.get("real")),
            "transcript": transcript,
            "reason": out.get("reason", ""),
        }
    )
