"""API-level walk of the demo path, against the stub pack.

Complements test_orchestrator.py: that one proves the engine, this one proves
the wiring between the engine and HTTP.
"""
import json
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from app import create_app  # noqa: E402
import catalogue  # noqa: E402
import mistral_client  # noqa: E402
import topics  # noqa: E402
from routes import friction as friction_routes  # noqa: E402
from routes.session import BLOCKING  # noqa: E402
from routes import coach as coach_routes  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_usage(tmp_path, monkeypatch):
    """Point topic usage at a scratch file.

    Selecting a topic spends it, so without this the suite would both mutate
    the real usage.json and 409 the moment two tests picked the same topic.
    """
    monkeypatch.setattr(catalogue, "USAGE_PATH", tmp_path / "usage.json")
    yield


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
    """Drive the feed: answer every coach conversation, clear every gate.

    Podcasts block a single prefetch batch but need no explicit action - the
    server needs nothing to hand over what comes next, the client just was not
    allowed to skip ahead of it. `stop` is checked after every card, so a test
    can end the walk at exactly the transition it cares about instead of
    guessing a card count.
    """
    seen = []
    while len(seen) < limit:
        cards = client.get("/api/session/{}/next?n={}".format(sid, n)).get_json()["cards"]
        for card in cards:
            seen.append(card["type"])
            if card["type"] == "coach":
                client.post(
                    "/api/session/{}/answer".format(sid),
                    json={"card_id": card["id"], "correct": correct},
                )
            elif card["type"] in ("math_gate", "touch_grass", "talk_to_human"):
                client.post("/api/session/{}/friction/clear".format(sid))
            if stop and stop(seen):
                return seen
    return seen


def after_first_check(seen):
    """True once a card follows the CHECK block - i.e. the branch was taken."""
    return "coach" in seen and seen[-1] != "coach"


def test_health(client):
    health = client.get("/api/health").get_json()
    assert health["ok"] is True
    assert health["realtime_stt_model"] == config.REALTIME_STT_MODEL


def test_conversation_gate_returns_transcript_and_reflection(client, monkeypatch):
    monkeypatch.setattr(
        friction_routes.mc,
        "transcribe_diarized",
        lambda *_args, **_kwargs: {
            "text": (
                "My day was pretty good. I went for a long walk after lunch. "
                "That sounds relaxing. Where did you go? I walked around the lake near home."
            ),
            "segments": [
                {"speaker": "speaker_0", "text": "My day was pretty good. I went for a long walk after lunch."},
                {"speaker": "speaker_1", "text": "That sounds relaxing. Where did you go?"},
                {"speaker": "speaker_0", "text": "I walked around the lake near home."},
            ],
        },
    )
    monkeypatch.setattr(
        friction_routes.mc,
        "chat_json",
        lambda *_args, **_kwargs: {
            "real": True,
            "reason": "You shared something specific and responded to a follow-up question.",
            "reflection": {
                "strengths": ["You shared a concrete detail.", "You responded to curiosity."],
                "next_step": "Invite the other person to explain their view first.",
                "follow_up": "What part feels most surprising to you?",
            },
        },
    )

    response = client.post(
        "/api/friction/talk",
        data={
            "audio": (io.BytesIO(b"fake webm"), "conversation.webm"),
            "prompt": "How has your day been so far?",
        },
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["pass"] is True
    assert "long walk" in payload["transcript"]
    assert {segment["speaker"] for segment in payload["segments"]} == {"speaker_0", "speaker_1"}
    assert len(payload["reflection"]["strengths"]) == 2
    assert payload["reflection"]["next_step"]


def test_realtime_coach_websocket_is_registered(client):
    rules = {rule.rule for rule in client.application.url_map.iter_rules() if rule.websocket}
    assert "/api/coach/realtime" in rules


def test_coach_reply_stream_interleaves_text_and_pcm(client, monkeypatch):
    monkeypatch.setattr(
        coach_routes,
        "_coach_payload",
        lambda *_args: {
            "transcript": "Plants use light.",
            "reply": "Good start. What comes next?",
            "understood": True,
            "done": False,
        },
    )
    monkeypatch.setattr(
        coach_routes.mc,
        "tts_stream",
        lambda *_args, **_kwargs: iter((b"\0" * 16, b"\1" * 16)),
    )

    response = client.post(
        "/api/coach/turn/stream",
        json={"text": "Plants use light.", "topic": "photosynthesis", "history": []},
    )
    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]

    assert response.status_code == 200
    assert "".join(e["text"] for e in events if e["type"] == "text_delta") == (
        "Good start. What comes next?"
    )
    assert sum(e["type"] == "audio" for e in events) == 2
    assert next(i for i, e in enumerate(events) if e["type"] == "audio") < max(
        i for i, e in enumerate(events) if e["type"] == "text_delta"
    )
    assert events[-1] == {"type": "result", "understood": True, "done": False}


def test_coach_text_completes_when_tts_stream_fails(client, monkeypatch):
    monkeypatch.setattr(
        coach_routes,
        "_coach_payload",
        lambda *_args: {
            "transcript": "Carbon comes from air.",
            "reply": "Correct. Carbon dioxide supplies it.",
            "understood": True,
            "done": False,
        },
    )

    def broken_tts(*_args, **_kwargs):
        raise RuntimeError("temporary voice failure")
        yield b""  # pragma: no cover - makes this a generator

    monkeypatch.setattr(coach_routes.mc, "tts_stream", broken_tts)
    response = client.post(
        "/api/coach/turn/stream",
        json={"text": "Carbon comes from air.", "topic": "photosynthesis"},
    )
    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]

    assert "".join(e["text"] for e in events if e["type"] == "text_delta") == (
        "Correct. Carbon dioxide supplies it."
    )
    assert any(e["type"] == "audio_error" for e in events)
    assert events[-1]["type"] == "result"


def test_unknown_session_404s(client):
    assert client.get("/api/session/nope/next").status_code == 404


def test_missing_topic_is_rejected(client):
    """There is no such thing as an unknown topic any more - anything the user
    types gets generated - so only malformed input is refused up front. Both
    checks short-circuit before any API call, keeping the suite offline."""
    assert client.post("/api/session", json={}).status_code == 400
    assert client.post("/api/session", json={"topic": "   "}).status_code == 400
    assert client.post("/api/session", json={"topic": "x" * 200}).status_code == 400


def test_cached_topic_starts_without_generating(client):
    """A pack already on disk must start instantly and hit no API."""
    if not (config.TOPICS_DIR / "photosynthesis.json").exists():
        pytest.skip("no pack; run: python -m tools.generate_content --stub")

    calls = []
    real = mistral_client.chat_json

    def spy(*a, **kw):
        calls.append(a)
        return real(*a, **kw)

    mistral_client.chat_json = spy
    try:
        res = client.post("/api/session", json={"topic": "photosynthesis"})
    finally:
        mistral_client.chat_json = real

    assert res.status_code == 200
    assert calls == [], "a cached topic must not call the model"


def test_slugify_collapses_phrasings():
    assert topics.slugify("How do Black Holes work?!") == "how-do-black-holes-work"
    assert topics.slugify("WW2") == topics.slugify("ww2")
    assert topics.slugify("") == "topic"
    assert len(topics.slugify("x" * 300)) <= 48


def test_prefetch_stops_at_blocking_cards(client, sid):
    """Regression: a prefetch that served past a quiz advanced session state
    for a card the client never showed, silently skipping quiz questions."""
    data = client.get("/api/session/{}/next?n=5".format(sid)).get_json()
    types = [c["type"] for c in data["cards"]]

    blocking_at = [i for i, t in enumerate(types) if t in BLOCKING]
    for i in blocking_at:
        assert i == len(types) - 1, "a blocking card must end the batch: {}".format(types)


def test_every_check_is_exactly_one_coach_conversation(client, sid):
    """With prefetch on, a CHECK must still deliver exactly one coach turn."""
    seen = walk(client, sid, correct=False, stop=after_first_check)
    assert seen.count("coach") == 1, seen


def test_failing_a_check_returns_to_learning(client, sid):
    seen = walk(client, sid, correct=False, stop=after_first_check)
    # A LEARN round mixes kinds rather than serving one kind at a time.
    assert len(set(seen[: config.LEARN_CARDS_PER_ROUND])) > 1, seen
    assert "coach" in seen
    assert seen[-1] in ("flashcard", "fun_fact", "podcast"), seen
    stage = client.get("/api/session/{}/progress".format(sid)).get_json()["progress"]["stage"]
    assert stage == "LEARN"


def test_passing_a_check_unlocks_videos_then_a_gate(client, sid):
    seen = walk(client, sid, correct=True, stop=lambda s: "math_gate" in s)
    assert seen.count("video") >= config.SCROLL_BUDGET
    assert "math_gate" in seen, seen
    # Videos must come after the coach conversation, never before.
    assert seen.index("coach") < seen.index("video")
    assert seen.index("video") < seen.index("math_gate")


def test_answer_requires_fields(client, sid):
    assert client.post("/api/session/{}/answer".format(sid), json={}).status_code == 400


def test_podcast_cards_carry_their_segment(client, sid):
    """The client must never need a second request mid-feed."""
    seen = walk(client, sid, correct=True, limit=40)
    if "podcast" not in seen:
        pytest.skip("podcast items not reached in this walk")

    # Re-walk a fresh session looking at payloads. The topic was spent by the
    # first walk, so hand it back before selecting it again.
    catalogue.reset(cycle_bump=False)
    sid2 = client.post("/api/session", json={"topic": "photosynthesis"}).get_json()["session_id"]
    for _ in range(40):
        cards = client.get("/api/session/{}/next?n=3".format(sid2)).get_json()["cards"]
        for card in cards:
            if card["type"] == "podcast":
                seg = card["payload"].get("segment")
                assert seg and seg.get("turns"), "podcast card lacks its segment"
                assert "total" in card["payload"]
                return
            if card["type"] == "coach":
                client.post(
                    "/api/session/{}/answer".format(sid2),
                    json={"card_id": card["id"], "correct": True},
                )
            elif card["type"] in ("math_gate", "touch_grass", "talk_to_human"):
                client.post("/api/session/{}/friction/clear".format(sid2))


def test_learn_round_mixes_card_kinds(client, sid):
    """A round is always flashcard, then fun fact, then podcast, in that
    fixed order - weakest-first alone buried podcasts behind every flashcard,
    and mastery-first bucketing alone let the order drift round to round."""
    cards = client.get("/api/session/{}/next?n=3".format(sid)).get_json()["cards"]
    kinds = [c["type"] for c in cards]
    assert kinds == ["flashcard", "fun_fact", "podcast"], kinds


def test_clearing_a_gate_returns_to_learning_while_material_remains(client, sid):
    """The happy path must keep teaching. The first gate after a CHECK buys
    another round of scroll rather than ending it outright - one toll for six
    videos would be a bad trade. Only the second gate in a row hands back new
    material - never straight to CHECK, which would mean new material only
    ever appeared by failing a quiz."""
    walk(client, sid, correct=True, stop=lambda s: "math_gate" in s)
    after_first_gate = walk(client, sid, correct=True, stop=lambda s: bool(s))
    assert after_first_gate[0] == "video", after_first_gate

    walk(client, sid, correct=True, stop=lambda s: "touch_grass" in s)
    after_second_gate = walk(client, sid, correct=True, stop=lambda s: bool(s))
    assert after_second_gate[0] in ("flashcard", "fun_fact", "podcast"), after_second_gate


def test_podcast_is_reachable_on_the_happy_path(client, sid):
    seen = walk(client, sid, correct=True, stop=lambda s: "podcast" in s, limit=12)
    assert "podcast" in seen, seen
