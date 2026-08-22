"""On-demand topic generation.

The user types any subject and gets a pack built for it by Mistral. Two rules
shape how this works:

1. Generation happens once per topic, at session start, behind a progress
   screen - never mid-scroll. The feed itself still serves entirely from disk,
   so scrolling never waits on an API.
2. Text and audio are split. Text (items, quiz, podcast script) is what the
   feed needs to start, and takes a few seconds. Rendering ~29 TTS clips takes
   far longer, so it runs in the background and the pack is rewritten when it
   lands. Until then PodcastCard falls back to its caption timer.
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import config
import content

# Background audio renders. Small pool: TTS is already parallel inside a render.
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts")

# slug -> {"stage": ..., "error": ...}. Guarded because Flask is threaded.
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

STAGE_TEXT = "text"        # writing flashcards, quiz, podcast script
STAGE_AUDIO = "audio"      # text is usable; voices still rendering
STAGE_READY = "ready"
STAGE_ERROR = "error"


class TopicRejected(Exception):
    """The model judged the input not to be a teachable subject."""


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "topic")[:48]


def _set(slug: str, **kw) -> None:
    with _LOCK:
        _JOBS.setdefault(slug, {}).update(kw)


def status(slug: str) -> dict[str, Any]:
    with _LOCK:
        job = dict(_JOBS.get(slug) or {})
    if not job:
        # Not generated this process - but it may be cached on disk already.
        if content.pack_exists(slug):
            pack = content.load_pack(slug)
            return {
                "stage": STAGE_READY if pack.get("audio_ready") else STAGE_AUDIO,
                "slug": slug,
            }
        return {"stage": "unknown", "slug": slug}
    job["slug"] = slug
    return job


def _render_audio_job(slug: str) -> None:
    """Background: render every podcast line, then rewrite the pack."""
    from tools import generate_content as gen

    try:
        pack = content.read_pack_file(slug)
        script = gen.render_audio(slug, pack["podcast"], quiet=True)
        pack["podcast"] = script
        pack["audio_ready"] = True
        content.write_pack_file(slug, pack)
        content.clear_cache()
        _set(slug, stage=STAGE_READY)
    except Exception as exc:  # noqa: BLE001
        # Audio is an enhancement, not a requirement - the captions still work.
        _set(slug, stage=STAGE_AUDIO, error=str(exc))


def ensure_pack(topic_text: str, *, want_audio: bool = True) -> tuple[str, dict]:
    """Return (slug, pack) for whatever the user typed, generating if needed.

    Blocks only for text generation. Audio is queued and lands later.
    """
    from tools import generate_content as gen

    slug = slugify(topic_text)

    # Already on disk from an earlier session or run.
    if content.pack_exists(slug):
        pack = content.load_pack(slug)
        if want_audio and not pack.get("audio_ready"):
            _kick_audio(slug)
        return slug, pack

    _set(slug, stage=STAGE_TEXT)
    try:
        meta = gen.gen_meta(topic_text)
        if not meta.get("ok", True):
            _set(slug, stage=STAGE_ERROR, error=meta.get("reason") or "Not a topic.")
            raise TopicRejected(meta.get("reason") or "That is not something I can teach.")

        meta = {
            "title": meta.get("title") or topic_text[:40],
            "emoji": meta.get("emoji") or "\U0001F4DA",
            "blurb": meta.get("blurb") or "",
        }
        # Re-slug from the tidied title so "ww2" and "WW2" share one pack.
        slug = slugify(meta["title"])
        if content.pack_exists(slug):
            return slug, content.load_pack(slug)

        _set(slug, stage=STAGE_TEXT, title=meta["title"], emoji=meta["emoji"])
        pack = gen.build_topic(slug, meta, skip_audio=True, quiet=True)
        content.write_pack_file(slug, pack)
        content.clear_cache()
    except TopicRejected:
        raise
    except Exception as exc:  # noqa: BLE001
        _set(slug, stage=STAGE_ERROR, error=str(exc))
        raise

    if want_audio:
        _kick_audio(slug)
    else:
        _set(slug, stage=STAGE_READY)

    return slug, content.load_pack(slug)


def _kick_audio(slug: str) -> None:
    with _LOCK:
        job = _JOBS.get(slug) or {}
        if job.get("stage") in (STAGE_AUDIO, STAGE_READY) and not job.get("error"):
            return  # already running or done
        _JOBS.setdefault(slug, {})["stage"] = STAGE_AUDIO
        _JOBS[slug].pop("error", None)
    _POOL.submit(_render_audio_job, slug)


SUGGESTIONS = [
    {"title": "Photosynthesis", "emoji": "\U0001F331"},
    {"title": "The French Revolution", "emoji": "\U0001F5FC"},
    {"title": "How HTTPS Works", "emoji": "\U0001F510"},
    {"title": "Black Holes", "emoji": "\U0001F30C"},
    {"title": "The Krebs Cycle", "emoji": "\U0001F52C"},
    {"title": "Roman Concrete", "emoji": "\U0001F3DB"},
]


def suggestions() -> list[dict]:
    """Chips for the picker: everything already cached, then some ideas."""
    cached = {t["slug"]: t for t in content.list_topics()}
    out = [dict(t, cached=True) for t in cached.values()]

    for s in SUGGESTIONS:
        slug = slugify(s["title"])
        if slug not in cached:
            out.append({"slug": slug, "title": s["title"], "emoji": s["emoji"],
                        "blurb": "", "cached": False})
    return out
