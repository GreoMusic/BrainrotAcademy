"""The no-repeats rule, tested without a server or a network.

A topic is spent when selected and cannot come back until every topic has been
spent, at which point the board resets into a new cycle.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import catalogue  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_usage(tmp_path, monkeypatch):
    """Never let a test touch the real usage file."""
    monkeypatch.setattr(catalogue, "USAGE_PATH", tmp_path / "usage.json")
    yield


def test_catalogue_is_two_levels_and_well_formed():
    assert len(catalogue.SUBJECTS) >= 5
    for s in catalogue.SUBJECTS:
        assert s["topics"], "{} has no topics".format(s["slug"])
        for t in s["topics"]:
            assert t["slug"] and t["title"]


def test_slugs_are_unique_across_subjects():
    seen = [t["slug"] for s in catalogue.SUBJECTS for t in s["topics"]]
    assert len(seen) == len(set(seen)), "duplicate topic slug"
    assert len(catalogue.ALL_SLUGS) == len(seen)


def test_lookup_resolves_subject_and_title():
    entry = catalogue.lookup("photosynthesis")
    assert entry["subject"] == "science"
    assert entry["title"] == "Photosynthesis"
    assert catalogue.lookup("nope") is None


def test_selecting_spends_a_topic():
    assert not catalogue.is_used("python")
    catalogue.mark_used("python")
    assert catalogue.is_used("python")
    assert "python" not in catalogue.remaining()


def test_a_spent_topic_stays_spent_across_reloads():
    """Usage lives on disk - a restart must not hand the topic back."""
    catalogue.mark_used("entropy")
    assert catalogue.state()["used"] == ["entropy"]
    # state() re-reads the file every call, so this is a genuine round-trip.
    assert catalogue.is_used("entropy")


def test_board_resets_only_when_every_topic_is_spent():
    slugs = sorted(catalogue.ALL_SLUGS)
    for slug in slugs[:-1]:
        out = catalogue.mark_used(slug)
        assert out["reset"] is False, "reset early at {}".format(slug)
        assert out["cycle"] == 1

    assert catalogue.remaining() == [slugs[-1]]

    final = catalogue.mark_used(slugs[-1])
    assert final["reset"] is True
    assert final["cycle"] == 2
    assert final["used"] == 0
    # Everything is selectable again.
    assert sorted(catalogue.remaining()) == slugs
    assert not catalogue.is_used(slugs[0])


def test_reselecting_the_same_topic_does_not_advance_the_cycle():
    catalogue.mark_used("python")
    for _ in range(5):
        out = catalogue.mark_used("python")
    assert out["used"] == 1
    assert out["cycle"] == 1
    assert out["reset"] is False


def test_free_text_topics_never_gate_the_cycle():
    """An off-catalogue topic is remembered, but must not make exhaustion
    unreachable - the board only counts catalogue slugs."""
    catalogue.mark_used("why-cats-purr")
    assert catalogue.state()["adhoc"] == ["why-cats-purr"]
    assert catalogue.state()["used"] == []
    assert len(catalogue.remaining()) == len(catalogue.ALL_SLUGS)

    for slug in catalogue.ALL_SLUGS:
        out = catalogue.mark_used(slug)
    assert out["reset"] is True


def test_unknown_slugs_in_the_file_do_not_block_exhaustion():
    """A topic removed from the catalogue must not linger in usage and stop
    the board ever reaching a reset."""
    catalogue._write({"used": ["a-retired-topic"], "cycle": 1, "adhoc": []})
    assert catalogue.state()["used"] == []

    slugs = sorted(catalogue.ALL_SLUGS)
    for slug in slugs[:-1]:
        catalogue.mark_used(slug)
    assert catalogue.mark_used(slugs[-1])["reset"] is True


def test_browse_reports_progress_per_subject():
    catalogue.mark_used("photosynthesis")
    view = catalogue.browse()

    science = next(s for s in view["subjects"] if s["slug"] == "science")
    photo = next(t for t in science["topics"] if t["slug"] == "photosynthesis")
    assert photo["used"] is True
    assert science["used"] == 1
    assert science["total"] == len(science["topics"])

    assert view["cycle"] == 1
    assert view["used"] == 1
    assert view["remaining"] == len(catalogue.ALL_SLUGS) - 1


def test_find_by_title_matches_free_text():
    assert catalogue.find_by_title("photosynthesis")["slug"] == "photosynthesis"
    assert catalogue.find_by_title("  Grammar & Punctuation ")["slug"] == "grammar-and-punctuation"
    assert catalogue.find_by_title("something else") is None


def test_corrupt_usage_file_is_survivable():
    catalogue.USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalogue.USAGE_PATH.write_text("{not json", encoding="utf-8")
    assert catalogue.state()["used"] == []
    assert catalogue.mark_used("python")["used"] == 1
