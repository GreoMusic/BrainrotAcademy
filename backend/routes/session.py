"""Session routes - the feed's only critical path.

`/next` deliberately does no network I/O: every card it serves comes from a
pre-generated pack on disk (plus this session's own gif batch, fetched once
at start), so the feed keeps working on bad wifi. `/session` already blocks
on Mistral for a new topic's text, so a GIPHY call there for a fresh reel
costs nothing the user does not already tolerate.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

import catalogue
import content
import giphy_client
import orchestrator as orch
import topics

bp = Blueprint("session", __name__, url_prefix="/api")

# In-memory. A refresh resets the session; acceptable for a 24h demo.
SESSIONS: dict[str, dict] = {}

# Cards that need the user to act before the engine can pick what comes next
# - answer a question, clear a gate, or (for podcast) finish listening.
# Prefetch stops at one of these: serving past it would advance session state
# for a card the client will not show, silently skipping content.
BLOCKING = {"quiz", "coach", "math_gate", "touch_grass", "talk_to_human", "podcast"}


def _get(session_id: str):
    state = SESSIONS.get(session_id)
    if state is None:
        return None, (jsonify({"error": "unknown session"}), 404)
    return state, None


@bp.get("/topics")
def list_topics():
    return jsonify({"topics": topics.suggestions()})


@bp.get("/topics/<slug>/status")
def topic_status(slug: str):
    """Polled by the podcast card while voices render in the background."""
    return jsonify(topics.status(slug))


@bp.get("/topics/<slug>/segment/<seg_id>")
def topic_segment(slug: str, seg_id: str):
    """Re-read one podcast segment.

    Lets a podcast card that started on captions alone pick up its audio once
    the background render finishes, without restarting the session.
    """
    try:
        pack = content.load_pack(slug)
    except content.TopicNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    seg = next(
        (s for s in pack.get("podcast", {}).get("segments", []) if s["id"] == seg_id), None
    )
    if seg is None:
        return jsonify({"error": "no such segment"}), 404
    return jsonify({"segment": seg, "audio_ready": bool(pack.get("audio_ready"))})


@bp.get("/catalogue")
def catalogue_view():
    """The two-level board, with what is spent and what is left this cycle."""
    return jsonify(catalogue.browse())


@bp.post("/session")
def start():
    """Start a session, either on a catalogue topic or on free text.

    Blocks for text generation (a few seconds on a new topic, instant on a
    cached one). Audio renders in the background and lands later.
    """
    body = request.get_json(silent=True) or {}
    slug_in = (body.get("slug") or "").strip()
    topic = (body.get("topic") or "").strip()

    entry = catalogue.lookup(slug_in) if slug_in else None
    if entry is None and topic:
        # Typing the name of a catalogue topic should select that topic, not
        # quietly mint a parallel copy of it under a different slug.
        entry = catalogue.find_by_title(topic)

    if entry is None and not topic:
        return jsonify({"error": "topic required"}), 400
    if len(topic) > 120:
        return jsonify({"error": "topic too long"}), 400

    # The no-repeats rule. Exhausting the board resets it, so a refusal here
    # always leaves the user something else to pick.
    if entry and catalogue.is_used(entry["slug"]):
        return jsonify(
            {
                "error": "You already did {} this cycle. Pick something else.".format(
                    entry["title"]
                ),
                "used": True,
            }
        ), 409

    try:
        if entry:
            meta = {
                "title": entry["title"],
                "emoji": entry["emoji"],
                "blurb": "{} - {}".format(entry["subject_title"], entry["title"]),
            }
            slug, pack = topics.ensure_pack(
                entry["title"], meta=meta, slug=entry["slug"]
            )
        else:
            slug, pack = topics.ensure_pack(topic)
    except topics.TopicRejected as exc:
        return jsonify({"error": str(exc), "rejected": True}), 422
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "could not build that topic: {}".format(exc)}), 502

    cycle = catalogue.mark_used(slug)

    # A pack is cached and replayed across every session on that topic, so
    # serving straight from its baked-in gifs would show the exact same reel
    # every time. A fresh batch here means every session opens on a reel
    # nobody has seen yet - this is the one network call session start
    # already tolerates (same as text generation), never the scroll path.
    fresh_gifs = giphy_client.brainrot(limit=16)

    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = orch.new_session(sid, slug, pack, gifs=fresh_gifs)
    return jsonify(
        {
            "session_id": sid,
            "topic": slug,
            "title": pack.get("title", slug),
            "emoji": pack.get("emoji", ""),
            "audio_ready": bool(pack.get("audio_ready")),
            "cycle": cycle,
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
    state = orch.clear_friction(state, content.load_pack(state["topic"]))
    return jsonify({"progress": orch.progress(state), "stage": state["stage"]})


@bp.get("/session/<sid>/progress")
def get_progress(sid: str):
    state, err = _get(sid)
    if err:
        return err
    return jsonify({"progress": orch.progress(state)})
