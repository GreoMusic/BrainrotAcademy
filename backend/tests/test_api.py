"""API-level walk of the demo path, against the stub pack.

Complements test_orchestrator.py: that one proves the engine, this one proves
the wiring between the engine and HTTP.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from app import create_app  # noqa: E402
from routes.session import BLOCKING  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture
def sid(client):
    if not (config.TOPICS_DIR / "photosynthesis.json").exists():
        pytest.skip("no pack; run: python -m tools.generate_content --stub")
    return client.post("/api/session", json={"topic": "photosynthesis"}).get_json()["session_id"]


def walk(client, sid, *, correct, limit=40, n=3, stop=None):
    """Drive the feed, answering every quiz and clearing every gate.

    `stop` is checked after every card, so a test can end the walk at exactly
    the transition it cares about instead of guessing a card count.
    """
    seen = []
    while len(seen) < limit:
        cards = client.get("/api/session/{}/next?n={}".format(sid, n)).get_json()["cards"]
        for card in cards:
            seen.append(card["type"])
            if card["type"] == "quiz":
                client.post(
                    "/api/session/{}/answer".format(sid),
                    json={
                        "card_id": card["id"],
                        "correct": correct,
                        "item_id": card["payload"]["item_id"],
                    },
                )
            elif card["type"] in BLOCKING:
                client.post("/api/session/{}/friction/clear".format(sid))
            if stop and stop(seen):
                return seen
    return seen


def after_first_check(seen):
    """True once a card follows the CHECK block - i.e. the branch was taken."""
    return "quiz" in seen and seen[-1] != "quiz"


def test_health(client):
    assert client.get("/api/health").get_json()["ok"] is True


def test_unknown_session_404s(client):
    assert client.get("/api/session/nope/next").status_code == 404


def test_unknown_topic_404s(client):
    assert client.post("/api/session", json={"topic": "nope"}).status_code == 404


def test_prefetch_stops_at_blocking_cards(client, sid):
    """Regression: a prefetch that served past a quiz advanced session state
    for a card the client never showed, silently skipping quiz questions."""
    data = client.get("/api/session/{}/next?n=5".format(sid)).get_json()
    types = [c["type"] for c in data["cards"]]

    blocking_at = [i for i, t in enumerate(types) if t in BLOCKING]
    for i in blocking_at:
        assert i == len(types) - 1, "a blocking card must end the batch: {}".format(types)


def test_every_quiz_in_a_check_is_served(client, sid):
    """With prefetch on, a full CHECK must still deliver all its questions."""
    seen = walk(client, sid, correct=False, stop=after_first_check)
    assert seen.count("quiz") == config.QUIZ_CARDS_PER_CHECK, seen


def test_failing_a_check_returns_to_learning(client, sid):
    seen = walk(client, sid, correct=False, stop=after_first_check)
    # A LEARN round mixes kinds rather than serving one kind at a time.
    assert len(set(seen[: config.LEARN_CARDS_PER_ROUND])) > 1, seen
    assert "quiz" in seen
    assert seen[-1] in ("flashcard", "fun_fact", "podcast"), seen
    stage = client.get("/api/session/{}/progress".format(sid)).get_json()["progress"]["stage"]
    assert stage == "LEARN"


def test_passing_a_check_unlocks_videos_then_a_gate(client, sid):
    seen = walk(client, sid, correct=True, stop=lambda s: "math_gate" in s)
    assert seen.count("video") >= config.SCROLL_BUDGET
    assert "math_gate" in seen, seen
    # Videos must come after the quiz, never before.
    assert seen.index("quiz") < seen.index("video")
    assert seen.index("video") < seen.index("math_gate")


def test_answer_requires_fields(client, sid):
    assert client.post("/api/session/{}/answer".format(sid), json={}).status_code == 400


def test_podcast_cards_carry_their_segment(client, sid):
    """The client must never need a second request mid-feed."""
    seen = walk(client, sid, correct=True, limit=40)
    if "podcast" not in seen:
        pytest.skip("podcast items not reached in this walk")

    # Re-walk a fresh session looking at payloads.
    sid2 = client.post("/api/session", json={"topic": "photosynthesis"}).get_json()["session_id"]
    for _ in range(40):
        cards = client.get("/api/session/{}/next?n=3".format(sid2)).get_json()["cards"]
        for card in cards:
            if card["type"] == "podcast":
                seg = card["payload"].get("segment")
                assert seg and seg.get("turns"), "podcast card lacks its segment"
                assert "total" in card["payload"]
                return
            if card["type"] == "quiz":
                client.post(
                    "/api/session/{}/answer".format(sid2),
                    json={"card_id": card["id"], "correct": True, "item_id": card["payload"]["item_id"]},
                )
            elif card["type"] in BLOCKING:
                client.post("/api/session/{}/friction/clear".format(sid2))


def test_learn_round_mixes_card_kinds(client, sid):
    """A round should be a flashcard AND a fun fact AND a podcast segment -
    weakest-first alone buried podcasts behind every flashcard."""
    cards = client.get("/api/session/{}/next?n=3".format(sid)).get_json()["cards"]
    kinds = [c["type"] for c in cards]
    assert len(set(kinds)) == len(kinds), "a LEARN round repeated a kind: {}".format(kinds)
    assert "podcast" in kinds, kinds


def test_clearing_a_gate_returns_to_learning_while_material_remains(client, sid):
    """The happy path must keep teaching. Sending every cleared gate straight to
    CHECK meant new material only ever appeared by failing a quiz."""
    seen = walk(client, sid, correct=True, stop=lambda s: s.count("math_gate") == 1)
    after = walk(client, sid, correct=True, stop=lambda s: bool(s))
    assert after[0] in ("flashcard", "fun_fact", "podcast"), after


def test_podcast_is_reachable_on_the_happy_path(client, sid):
    seen = walk(client, sid, correct=True, stop=lambda s: "podcast" in s, limit=12)
    assert "podcast" in seen, seen
