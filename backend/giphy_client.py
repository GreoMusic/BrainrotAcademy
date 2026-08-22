"""GIPHY - real reel content for the doomscroll feed.

Fetched once per topic at generation time, same as the podcast audio and quiz
bank: nothing on the scroll path calls an API, so this runs offline and the
URLs get baked into the pack. The clips themselves stream straight from
GIPHY's CDN in the browser - the backend never proxies the bytes.
"""
from __future__ import annotations

import random

import httpx

import config

BASE = "https://api.giphy.com/v1/gifs"

# Actual brainrot, not just whatever GIPHY calls trending - trending skews
# toward news and sports reactions, which reads as a normal meme feed, not
# the mindless algorithmic slop this stage is supposed to be a taste of.
BRAINROT_QUERIES = [
    "skibidi toilet",
    "subway surfers gameplay",
    "italian brainrot",
    "sigma",
    "gyat rizz",
    "ohio meme",
    "fanum tax",
    "gigachad",
    "npc meme",
    "mewing",
]


def _to_clips(entries: list[dict]) -> list[dict]:
    out = []
    for g in entries:
        images = g.get("images", {})
        mp4 = (
            (images.get("original_mp4") or {}).get("mp4")
            or (images.get("looping") or {}).get("mp4")
            or (images.get("downsized_medium") or {}).get("mp4")
        )
        if not mp4:
            continue
        out.append(
            {
                "id": "gif_" + g.get("id", ""),
                "src": mp4,
                "caption": (g.get("title") or "").strip() or "brainrot",
                "giphy_url": g.get("url", ""),
            }
        )
    return out


def search(query: str, *, limit: int = 8, rating: str = "pg-13") -> list[dict]:
    if not config.GIPHY_API_KEY:
        return []
    try:
        resp = httpx.get(
            "{}/search".format(BASE),
            params={
                "api_key": config.GIPHY_API_KEY,
                "q": query,
                "limit": limit,
                "rating": rating,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return _to_clips(resp.json().get("data", []))
    except Exception:  # noqa: BLE001
        # A missing/bad key or a flaky network must not block content
        # generation - the reel just falls back to whatever real clips exist.
        return []


def brainrot(*, limit: int = 8, n_queries: int = 3) -> list[dict]:
    """A mixed batch of actual brainrot content, not generic trending.

    Samples a few terms from BRAINROT_QUERIES each call so a topic's reel
    isn't the exact same handful of clips every time it is regenerated.
    """
    if not config.GIPHY_API_KEY:
        return []

    per_query = max(1, limit // n_queries)
    out: list[dict] = []
    seen_ids = set()
    for q in random.sample(BRAINROT_QUERIES, min(n_queries, len(BRAINROT_QUERIES))):
        for clip in search(q, limit=per_query):
            if clip["id"] in seen_ids:
                continue
            seen_ids.add(clip["id"])
            out.append(clip)
    return out[:limit]
