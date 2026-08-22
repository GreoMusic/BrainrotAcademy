"""The transition engine.

    LEARN -> CHECK -> SCROLL -> FRICTION -> CHECK -> ...
               |
               +-- fail --> LEARN (with the missed items boosted to the front)

This is the heart of the app and the part most likely to need debugging at 3am,
so it is written as pure functions over a plain dict. No Flask, no globals, no
network. tests/test_orchestrator.py drives it directly.
"""
from __future__ import annotations

import random
from typing import Any

import config

LEARN, CHECK, SCROLL, FRICTION = "LEARN", "CHECK", "SCROLL", "FRICTION"

# Rotated through so a long session does not repeat the same gate.
FRICTION_KINDS = ["math_gate", "touch_grass", "talk_to_human"]

# A LEARN round always teaches in this order - flashcard, then fun fact, then
# podcast - so the loop reads the same every round instead of drifting toward
# whichever kind currently has the lowest mastery.
KIND_ORDER = ["flashcard", "fun_fact", "podcast"]

MASTERY_UP = 0.34
MASTERY_DOWN = 0.25
# An item counts as "known" past this, and stops being drawn for LEARN.
KNOWN_AT = 0.67


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def new_session(session_id: str, topic: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Fresh session state. pack is the pre-generated topic content."""
    return {
        "id": session_id,
        "topic": topic,
        "stage": LEARN,
        "mastery": {item["id"]: 0.0 for item in pack.get("items", [])},
        "served_count": {},          # card_id -> times shown
        "pending": [],               # cards queued for the current stage
        "scroll_budget": 0,
        "videos_watched": 0,
        "video_cursor": 0,
        "friction_cursor": 0,
        "round": 0,
        "check_answers": [],         # bools for the in-flight CHECK
        "missed": [],                # item ids to re-teach next LEARN
        "learn_dealt": False,        # a LEARN batch is out; next refill checks
        "history": [],
    }


# ---------------------------------------------------------------------------
# selection helpers
# ---------------------------------------------------------------------------
def _items_by_need(state: dict, pack: dict) -> list[dict]:
    """Weakest-first, with previously-missed items jumped to the front."""
    by_id = {i["id"]: i for i in pack.get("items", [])}
    missed = [by_id[i] for i in state["missed"] if i in by_id]

    rest = [
        it
        for it in pack.get("items", [])
        if it["id"] not in state["missed"]
        and state["mastery"].get(it["id"], 0.0) < KNOWN_AT
    ]
    rest.sort(
        key=lambda it: (
            state["mastery"].get(it["id"], 0.0),
            state["served_count"].get(it["id"], 0),
        )
    )

    # Round-robin across kinds, in KIND_ORDER, so one LEARN round is a
    # flashcard AND a fun fact AND a podcast segment, always in that order.
    # Plain weakest-first would serve all six flashcards before the first
    # podcast ever appeared, and bucketing by mastery order alone would let
    # the sequence drift round to round.
    buckets: dict[str, list[dict]] = {}
    for it in rest:
        buckets.setdefault(it.get("kind", "flashcard"), []).append(it)
    order = KIND_ORDER + [k for k in buckets if k not in KIND_ORDER]

    mixed = []
    while buckets:
        for kind in order:
            if kind in buckets:
                mixed.append(buckets[kind].pop(0))
                if not buckets[kind]:
                    del buckets[kind]

    return missed + mixed


def _card_for_item(item: dict, pack: dict) -> dict:
    """An item renders as whichever card type it declares.

    Podcast items are hydrated with their full segment (turns + audio urls) so
    the client never has to make a second request mid-feed.
    """
    payload = dict(item)
    if item.get("kind") == "podcast":
        segments = pack.get("podcast", {}).get("segments", [])
        seg = next((s for s in segments if s["id"] == item.get("segment_id")), None)
        payload["segment"] = seg
        payload["index"] = segments.index(seg) if seg else 0
        payload["total"] = len(segments)
        # The card polls this slug for its voices, which render in background.
        payload["topic"] = pack.get("topic")
    return {"type": item.get("kind", "flashcard"), "id": item["id"], "payload": payload}


def _coach_card(state: dict, pack: dict) -> dict:
    """A conversation instead of a quiz. Counts as a whole CHECK on its own."""
    weakest = sorted(state["mastery"], key=lambda k: state["mastery"].get(k, 0.0))
    focus = next(
        (i for i in pack.get("items", []) if weakest and i["id"] == weakest[0]), None
    )
    subject = (focus or {}).get("front") or (focus or {}).get("text") or pack.get("title", "")
    return {
        "type": "coach",
        "id": "coach:{}".format(state["round"]),
        "payload": {
            "topic": state["topic"],
            "focus": subject,
            "opener": "Alright — no multiple choice this time. {}".format(
                "In your own words: {}".format(subject) if subject else "Tell me what you remember."
            ),
        },
    }


def _video_card(state: dict, pack: dict) -> dict:
    clips = pack.get("clips", [])
    if not clips:
        return {"type": "video", "id": "video:none", "payload": {"src": None}}
    clip = clips[state["video_cursor"] % len(clips)]
    state["video_cursor"] += 1
    return {"type": "video", "id": "video:" + str(clip["id"]), "payload": clip}


def _friction_card(state: dict) -> dict:
    kind = FRICTION_KINDS[state["friction_cursor"] % len(FRICTION_KINDS)]
    state["friction_cursor"] += 1
    payload: dict[str, Any] = {"kind": kind, "topic": state["topic"]}
    if kind == "math_gate":
        payload.update(make_math_problem(state["round"]))
    card_id = "friction:{}:{}".format(kind, state["friction_cursor"])
    return {"type": kind, "id": card_id, "payload": payload}


def make_math_problem(difficulty: int = 0) -> dict[str, Any]:
    """Local generation - a friction gate must never wait on the network."""
    rng = random.Random()
    if difficulty < 1:
        a, b = rng.randint(4, 12), rng.randint(3, 9)
        return {"question": "{} x {}".format(a, b), "answer": a * b}
    a, b, c = rng.randint(3, 14), rng.randint(2, 9), rng.randint(5, 30)
    return {"question": "{} x {} + {}".format(a, b, c), "answer": a * b + c}


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------
def next_card(state: dict, pack: dict) -> tuple[dict, dict]:
    """Return the next card and the advanced state.

    Mutates and returns state (callers treat it as owned). Loops a bounded
    number of times as stages hand off to one another.
    """
    for _ in range(len(FRICTION_KINDS) + 6):  # generous bound; guards typos
        if state["pending"]:
            card = state["pending"].pop(0)
            card["stage"] = state["stage"]
            state["history"].append(
                {"id": card["id"], "stage": state["stage"], "type": card["type"]}
            )
            state["served_count"][card["id"]] = state["served_count"].get(card["id"], 0) + 1
            return card, state

        _refill(state, pack)

    raise RuntimeError("transition engine stalled in stage " + state["stage"])


def _refill(state: dict, pack: dict) -> None:
    """Queue the next stage's cards, transitioning if the stage is done."""
    stage = state["stage"]

    if stage == LEARN:
        items = [] if state["learn_dealt"] else _items_by_need(state, pack)
        items = items[: config.LEARN_CARDS_PER_ROUND]
        if items:
            # Exactly one batch per round, then go prove it. Dealing until the
            # item pool empties would strand the user in LEARN forever.
            state["pending"] = [_card_for_item(it, pack) for it in items]
            state["missed"] = []
            state["learn_dealt"] = True
        else:
            state["stage"] = CHECK
            state["learn_dealt"] = False

    elif stage == CHECK:
        if state["check_answers"]:
            _resolve_check(state)
        else:
            # Always a conversation, never multiple choice - the user proves
            # it by talking it through, every round.
            state["pending"] = [_coach_card(state, pack)]

    elif stage == SCROLL:
        if state["scroll_budget"] > 0:
            state["scroll_budget"] -= 1
            state["videos_watched"] += 1
            state["pending"] = [_video_card(state, pack)]
        else:
            state["stage"] = FRICTION

    elif stage == FRICTION:
        state["pending"] = [_friction_card(state)]

    else:
        raise RuntimeError("unknown stage " + repr(stage))


def _resolve_check(state: dict) -> None:
    """Score the finished CHECK and branch."""
    answers = state["check_answers"]
    score = sum(1 for a in answers if a) / len(answers)
    state["check_answers"] = []
    state["round"] += 1
    state["last_score"] = score

    if score >= config.PASS_THRESHOLD:
        state["stage"] = SCROLL
        state["scroll_budget"] = config.SCROLL_BUDGET
    else:
        state["stage"] = LEARN
        state["learn_dealt"] = False


def record_answer(
    state: dict, card_id: str, correct: bool, item_id: str | None = None
) -> dict:
    """Fold a quiz result into mastery, and remember misses for re-teaching."""
    item_id = item_id or card_id.replace("quiz:", "", 1)
    cur = state["mastery"].get(item_id, 0.0)
    state["mastery"][item_id] = (
        min(1.0, cur + MASTERY_UP) if correct else max(0.0, cur - MASTERY_DOWN)
    )

    if state["stage"] == CHECK:
        state["check_answers"].append(correct)
        # A coach conversation IS the whole check, so resolve it immediately
        # rather than waiting for peers that will never arrive.
        if card_id.startswith("coach:"):
            state["pending"] = []
        if not correct and item_id not in state["missed"]:
            state["missed"].append(item_id)

    return state


def clear_friction(state: dict, pack: dict | None = None) -> dict:
    """A passed friction gate resumes the loop.

    Back to LEARN while there is still material to teach, otherwise into a
    review CHECK. Always going to CHECK meant the happy path taught three cards
    and then never taught anything again - you only saw new material by failing.
    """
    if state["stage"] != FRICTION:
        return state

    state["pending"] = []
    has_more = bool(pack and _items_by_need(state, pack))
    state["stage"] = LEARN if has_more else CHECK
    state["learn_dealt"] = False
    return state


def progress(state: dict) -> dict[str, Any]:
    """What the HUD renders."""
    mastery = state["mastery"]
    total = len(mastery) or 1
    return {
        "stage": state["stage"],
        "topic": state["topic"],
        "mastered": sum(1 for v in mastery.values() if v >= KNOWN_AT),
        "total": len(mastery),
        "mastery_pct": round(100 * sum(mastery.values()) / total),
        "scroll_budget": state["scroll_budget"],
        "videos_watched": state["videos_watched"],
        "round": state["round"],
        "last_score": state.get("last_score"),
    }
