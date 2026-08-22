"""GIPHY is best-effort content for the reel - a missing key or a bad
response must never fail a build, only leave the reel a little thinner."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import giphy_client  # noqa: E402


def test_search_returns_empty_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "GIPHY_API_KEY", "")
    assert giphy_client.search("cats") == []


def test_brainrot_returns_empty_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "GIPHY_API_KEY", "")
    assert giphy_client.brainrot() == []


def test_search_survives_a_network_failure(monkeypatch):
    monkeypatch.setattr(config, "GIPHY_API_KEY", "fake-key-for-test")

    def boom(*a, **kw):
        raise ConnectionError("no network")

    monkeypatch.setattr(giphy_client.httpx, "get", boom)
    assert giphy_client.search("cats") == []


def test_brainrot_samples_multiple_queries_and_dedupes(monkeypatch):
    monkeypatch.setattr(config, "GIPHY_API_KEY", "fake-key-for-test")

    calls = []

    def fake_search(query, *, limit=8, rating="pg-13"):
        calls.append(query)
        # Two different queries "coincidentally" surface the same clip once.
        return [{"id": "gif_shared", "src": "https://giphy.com/shared.mp4",
                 "caption": query, "giphy_url": ""}]

    monkeypatch.setattr(giphy_client, "search", fake_search)
    out = giphy_client.brainrot(limit=8, n_queries=3)

    assert len(calls) == 3, calls
    assert len(set(calls)) == 3, "should sample distinct queries"
    assert len(out) == 1, "duplicate clip ids across queries must be deduped"


def test_to_clips_skips_entries_without_an_mp4():
    entries = [
        {"id": "a", "title": "no mp4 here", "images": {}, "url": "https://giphy.com/a"},
        {
            "id": "b",
            "title": "has mp4",
            "images": {"original_mp4": {"mp4": "https://giphy.com/b.mp4"}},
            "url": "https://giphy.com/b",
        },
    ]
    out = giphy_client._to_clips(entries)
    assert len(out) == 1
    assert out[0]["id"] == "gif_b"
    assert out[0]["src"] == "https://giphy.com/b.mp4"
    assert out[0]["caption"] == "has mp4"
    assert out[0]["giphy_url"] == "https://giphy.com/b"
