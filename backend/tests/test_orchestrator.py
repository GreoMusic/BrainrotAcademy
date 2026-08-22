"""Drive the transition engine directly - no Flask, no network, no UI.

If this file is green, the core of the app works and any bug is in the wiring.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import orchestrator as orch  # noqa: E402


def make_pack(n_items=6, n_clips=4):
    """Minimal stand-in for a generated topic pack."""
    items = [
        {"id": "i{}".format(k), "kind": "flashcard", "front": "q{}".format(k), "back": "a{}".format(k)}
        for k in range(n_items)
    ]
    return {
        "topic": "test",
        "items": items,
        "quiz": [
            {
                "item_id": it["id"],
                "q": "quiz for " + it["id"],
                "options": ["a", "b", "c"],
                "correct": 1,
            }
            for it in items
        ],
        "clips": [{"id": "c{}".format(k), "src": "/clips/c{}.mp4".format(k)} for k in range(n_clips)],
    }


def drain(state, pack, n):
    """Pull n cards, answering nothing."""
    out = []
    for _ in range(n):
        card, state = orch.next_card(state, pack)
        out.append(card)
    return out, state


def answer_check(state, pack, correct, item_id=None):
    """Walk the one-card CHECK - always a coach conversation now."""
    card, state = orch.next_card(state, pack)
    assert card["type"] == "coach", "expected coach, got {}".format(card["type"])
    state = orch.record_answer(state, card["id"], correct, item_id)
    return state


# ---------------------------------------------------------------------------


def test_starts_in_learn_and_serves_learning_cards():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    assert s["stage"] == orch.LEARN

    cards, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)
    assert all(c["type"] == "flashcard" for c in cards)
    assert len({c["id"] for c in cards}) == config.LEARN_CARDS_PER_ROUND


def test_learn_hands_off_to_check():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)

    card, s = orch.next_card(s, pack)
    assert card["type"] == "coach"
    assert s["stage"] == orch.CHECK


def test_failed_check_loops_back_to_learn_and_reteaches_missed():
    """The money shot: get the conversation wrong, land back in LEARN on that
    exact item."""
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)

    s = answer_check(s, pack, False, item_id="i0")
    assert s["missed"] == ["i0"], "failed answers should be recorded as missed"

    card, s = orch.next_card(s, pack)
    assert s["stage"] == orch.LEARN, "a failed CHECK must return to LEARN"
    assert card["type"] == "flashcard"
    assert card["id"] == "i0", "the missed item must be re-taught first"
    assert s["last_score"] < config.PASS_THRESHOLD


def test_passed_check_unlocks_scroll_budget():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)

    s = answer_check(s, pack, True)

    card, s = orch.next_card(s, pack)
    assert s["stage"] == orch.SCROLL
    assert card["type"] == "video"
    # One video already consumed from the granted budget.
    assert s["scroll_budget"] == config.SCROLL_BUDGET - 1


def test_scroll_budget_exhausts_into_friction():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)
    s = answer_check(s, pack, True)

    cards, s = drain(s, pack, config.SCROLL_BUDGET)
    assert all(c["type"] == "video" for c in cards)
    assert s["scroll_budget"] == 0

    gate, s = orch.next_card(s, pack)
    assert s["stage"] == orch.FRICTION
    assert gate["type"] in orch.FRICTION_KINDS
    assert gate["type"] == "math_gate", "first gate should be the offline-safe one"
    assert gate["payload"]["answer"] == eval(gate["payload"]["question"].replace("x", "*"))


def test_cleared_friction_returns_to_check():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)
    s = answer_check(s, pack, True)
    _, s = drain(s, pack, config.SCROLL_BUDGET)
    _, s = orch.next_card(s, pack)  # the gate

    s = orch.clear_friction(s)
    assert s["stage"] == orch.CHECK

    card, s = orch.next_card(s, pack)
    assert card["type"] == "coach"


def test_full_stage_sequence():
    """Assert the exact stage order the plan promises."""
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    seen = []

    def note(state):
        if not seen or seen[-1] != state["stage"]:
            seen.append(state["stage"])

    for _ in range(config.LEARN_CARDS_PER_ROUND):
        card, s = orch.next_card(s, pack)
        note(s)
    s = answer_check(s, pack, True)
    note(s)
    for _ in range(config.SCROLL_BUDGET):
        card, s = orch.next_card(s, pack)
        note(s)
    _, s = orch.next_card(s, pack)
    note(s)
    s = orch.clear_friction(s)
    _, s = orch.next_card(s, pack)
    note(s)

    assert seen == [orch.LEARN, orch.CHECK, orch.SCROLL, orch.FRICTION, orch.CHECK], seen


def test_mastery_rises_and_falls():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    s = orch.record_answer(s, "quiz:i0", True)
    assert s["mastery"]["i0"] > 0
    high = s["mastery"]["i0"]
    s = orch.record_answer(s, "quiz:i0", False)
    assert s["mastery"]["i0"] < high
    # Never escapes [0, 1].
    for _ in range(10):
        s = orch.record_answer(s, "quiz:i0", False)
    assert s["mastery"]["i0"] == 0.0
    for _ in range(10):
        s = orch.record_answer(s, "quiz:i0", True)
    assert s["mastery"]["i0"] == 1.0


def test_friction_kinds_rotate():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    kinds = [orch._friction_card(s)["type"] for _ in range(len(orch.FRICTION_KINDS) + 1)]
    assert kinds[: len(orch.FRICTION_KINDS)] == orch.FRICTION_KINDS
    assert kinds[-1] == orch.FRICTION_KINDS[0], "should wrap around"


def test_engine_never_stalls_over_a_long_session():
    """Guard against a stage failing to hand off - the 3am bug."""
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    for n in range(200):
        card, s = orch.next_card(s, pack)
        assert card["type"], "card {} had no type".format(n)
        if card["type"] == "coach":
            s = orch.record_answer(s, card["id"], n % 3 != 0)
        elif card["type"] in orch.FRICTION_KINDS:
            s = orch.clear_friction(s, pack)


def test_progress_shape():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    p = orch.progress(s)
    assert p["total"] == 6 and p["mastered"] == 0 and p["mastery_pct"] == 0
    s = orch.record_answer(s, "quiz:i0", True)
    s = orch.record_answer(s, "quiz:i0", True)
    assert orch.progress(s)["mastered"] == 1


def test_every_check_is_a_coach_conversation():
    """CHECK is always a coach conversation now - never multiple choice."""
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    _, s = drain(s, pack, config.LEARN_CARDS_PER_ROUND)

    card, s = orch.next_card(s, pack)
    assert card["type"] == "coach"


def test_a_coach_conversation_resolves_the_whole_check():
    """The coach is one card standing in for a full CHECK, so a single
    answer must end the CHECK instead of waiting for peers that never come."""
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    s["stage"] = orch.CHECK

    card, s = orch.next_card(s, pack)
    assert card["type"] == "coach"

    s = orch.record_answer(s, card["id"], True)
    nxt, s = orch.next_card(s, pack)
    assert s["stage"] == orch.SCROLL, "passing the coach should unlock scrolling"
    assert nxt["type"] == "video"


def test_failing_the_coach_returns_to_learning():
    pack = make_pack()
    s = orch.new_session("s1", "test", pack)
    s["stage"] = orch.CHECK

    card, s = orch.next_card(s, pack)
    s = orch.record_answer(s, card["id"], False)
    nxt, s = orch.next_card(s, pack)
    assert s["stage"] == orch.LEARN
    assert nxt["type"] in ("flashcard", "fun_fact", "podcast")


def test_a_learn_round_mixes_kinds():
    """A LEARN round always teaches flashcard, then fun fact, then podcast -
    weakest-first alone buried podcast segments behind every flashcard, and
    mastery-first bucketing alone let the order drift round to round."""
    pack = make_pack()
    pack["items"] += [
        {"id": "ff1", "kind": "fun_fact", "text": "x"},
        {"id": "pod_s1", "kind": "podcast", "segment_id": "s1"},
    ]
    pack["podcast"] = {"segments": [{"id": "s1", "turns": [{"id": "t1", "text": "hi"}]}]}
    s = orch.new_session("s1", "test", pack)

    cards, s = drain(s, pack, 3)
    kinds = [c["type"] for c in cards]
    assert kinds == ["flashcard", "fun_fact", "podcast"], kinds


def test_clearing_a_gate_resumes_learning_while_material_remains():
    """Sending every cleared gate to CHECK meant the happy path taught one
    round and then never taught anything again."""
    pack = make_pack(n_items=12)
    s = orch.new_session("s1", "test", pack)
    s["stage"] = orch.FRICTION

    s = orch.clear_friction(s, pack)
    assert s["stage"] == orch.LEARN

    # With everything mastered there is nothing left to teach -> review instead.
    s["stage"] = orch.FRICTION
    for k in s["mastery"]:
        s["mastery"][k] = 1.0
    s = orch.clear_friction(s, pack)
    assert s["stage"] == orch.CHECK
