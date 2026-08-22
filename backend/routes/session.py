"""Session routes - the feed's only critical path.

Deliberately does no network I/O: every card served here comes from a
pre-generated pack on disk, so the feed keeps working on bad wifi.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

import content
import orchestrator as orch

bp = Blueprint("session", __name__, url_prefix="/api")

# In-memory. A refresh resets the session; acceptable for a 24h demo.
SESSIONS: dict[str, dict] = {}

# Cards that need the user's answer before the engine can pick what comes next.
# Prefetch stops at one of these: serving past it would advance session state
# for a card the client will not show, silently skipping content.
BLOCKING = {"quiz", "math_gate", "touch_grass", "talk_to_human"}


def _get(session_id: str):
    state = SESSIONS.get(session_id)
    if state is None:
        return None, (jsonify({"error": "unknown session"}), 404)
    return state, None


@bp.get("/topics")
def topics():
    return jsonify({"topics": content.list_topics()})


@bp.post("/session")
def start():
    body = request.get_json(silent=True) or {}
    topic = body.get("topic")
    if not topic:
        return jsonify({"error": "topic required"}), 400
    try:
        pack = content.load_pack(topic)
    except content.TopicNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = orch.new_session(sid, topic, pack)
    return jsonify(
        {
            "session_id": sid,
            "topic": topic,
            "title": pack.get("title", topic),
            "progress": orch.progress(SESSIONS[sid]),
        }
    )


@bp.get("/session/<sid>/next")
def next_card(sid: str):
    state, err = _get(sid)
    if err:
        return err
    pack = content.load_pack(state["topic"])

    n = max(1, min(int(request.args.get("n", 1)), 5))  # prefetch a small window
    cards = []
    for _ in range(n):
        card, state = orch.next_card(state, pack)
        cards.append(card)
        if card["type"] in BLOCKING:
            break

    return jsonify({"cards": cards, "progress": orch.progress(state)})


@bp.post("/session/<sid>/answer")
def answer(sid: str):
    """Record a quiz result. Grading happens client-side for multiple choice;
    free-text answers are graded by /api/coach/grade first."""
    state, err = _get(sid)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    card_id = body.get("card_id")
    if card_id is None or "correct" not in body:
        return jsonify({"error": "card_id and correct required"}), 400

    state = orch.record_answer(
        state, card_id, bool(body["correct"]), body.get("item_id")
    )
    return jsonify({"progress": orch.progress(state), "stage": state["stage"]})


@bp.post("/session/<sid>/friction/clear")
def friction_clear(sid: str):
    state, err = _get(sid)
    if err:
        return err
    state = orch.clear_friction(state)
    return jsonify({"progress": orch.progress(state), "stage": state["stage"]})


@bp.get("/session/<sid>/progress")
def get_progress(sid: str):
    state, err = _get(sid)
    if err:
        return err
    return jsonify({"progress": orch.progress(state)})
