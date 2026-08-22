"""Session and gate-lifecycle routes.

`/next` deliberately does no network I/O: cards come from a pre-generated pack
plus the session's GIF batch. Session creation may fetch GIPHY content, and
user-triggered gate verification may call Mistral.
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

import catalogue
import content
import giphy_client
import mistral_client as mc
import orchestrator as orch
import topics

bp = Blueprint("session", __name__, url_prefix="/api")

# In-memory. A refresh resets the session; acceptable for a 24h demo.
SESSIONS: dict[str, dict] = {}
MAX_MATH_PHOTO_BYTES = 10 * 1024 * 1024
_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")

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


@bp.post("/catalogue/reset")
def catalogue_reset():
    """Start a fresh cycle so every built-in topic is selectable again."""
    catalogue.reset(cycle_bump=True)
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


@bp.post("/session/<sid>/coach/recover")
def coach_recover(sid: str):
    """A real-world reset can earn the break after a failed coach check."""
    state, err = _get(sid)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    card_id = body.get("card_id")
    if not card_id:
        return jsonify({"error": "card_id required"}), 400

    state = orch.recover_failed_check(state, card_id, body.get("item_id"))
    return jsonify({"progress": orch.progress(state), "stage": state["stage"]})


def _number_from_ocr(value) -> Decimal | None:
    """Normalize OCR decoration such as '$42$', 'x = 42', or '42.0'."""
    if value is None:
        return None
    matches = _NUMBER_RE.findall(str(value).replace(",", "").replace("−", "-"))
    if not matches:
        return None
    try:
        return Decimal(matches[-1])
    except InvalidOperation:
        return None


@bp.post("/session/<sid>/friction/math")
def grade_math(sid: str):
    """Check a typed answer or OCR a notebook photo, always server-side."""
    state, err = _get(sid)
    if err:
        return err

    active = state.get("active_friction") or {}
    card_id = (request.form.get("card_id") or "").strip()
    if (
        state.get("stage") != orch.FRICTION
        or active.get("kind") != "math_gate"
        or active.get("card_id") != card_id
    ):
        return jsonify({"error": "that math gate is not active"}), 409

    if "answer" in request.form:
        submitted = (request.form.get("answer") or "").strip()
        try:
            value = Decimal(submitted.replace(",", ""))
        except InvalidOperation:
            return jsonify(
                {"pass": False, "reason": "Enter a valid number and try again."}
            )
        if not value.is_finite():
            return jsonify(
                {"pass": False, "reason": "Enter a valid number and try again."}
            )

        correct = value == Decimal(str(active["answer"]))
        return jsonify(
            {
                "pass": correct,
                "recognized_answer": submitted,
                "reason": "Correct!" if correct else "Not quite. Check your work and try again.",
            }
        )

    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "photo required"}), 400
    mime = (photo.mimetype or "").lower()
    if not mime.startswith("image/"):
        return jsonify({"error": "photo must be an image"}), 415

    image_bytes = photo.read(MAX_MATH_PHOTO_BYTES + 1)
    if len(image_bytes) > MAX_MATH_PHOTO_BYTES:
        return jsonify({"error": "photo must be 10 MB or smaller"}), 413
    if not image_bytes:
        return jsonify({"error": "photo is empty"}), 400

    try:
        result = mc.ocr_math_answer(
            image_bytes,
            active["question"],
            mime=mime,
        )
    except Exception:  # noqa: BLE001
        return jsonify({"error": "could not read the photo; please try again"}), 502

    recognized = result.get("final_answer")
    value = _number_from_ocr(recognized)
    correct = value is not None and value == Decimal(str(active["answer"]))
    if value is None:
        reason = "I couldn't find a final numeric answer. Box or circle it, then retake the photo."
    elif correct:
        reason = "I read your final answer as {}. Correct!".format(recognized)
    else:
        reason = "I read your final answer as {}. Check your work and try again.".format(
            recognized
        )

    return jsonify(
        {
            "pass": correct,
            "recognized_answer": recognized,
            "reason": reason,
        }
    )


@bp.get("/session/<sid>/progress")
def get_progress(sid: str):
    state, err = _get(sid)
    if err:
        return err
    return jsonify({"progress": orch.progress(state)})
