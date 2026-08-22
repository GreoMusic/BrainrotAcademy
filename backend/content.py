"""Loading pre-generated topic packs off disk.

Nothing on the scroll path may call an API, so the feed is served entirely
from these packs. tools/generate_content.py writes them.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import config


class TopicNotFound(Exception):
    pass


def pack_path(slug: str) -> "Path":
    return config.TOPICS_DIR / "{}.json".format(slug)


def pack_exists(slug: str) -> bool:
    p = pack_path(slug)
    return p.exists() and p.stat().st_size > 0


def read_pack_file(slug: str) -> dict[str, Any]:
    """Raw read, bypassing the cache - used by the background audio render."""
    return json.loads(pack_path(slug).read_text(encoding="utf-8"))


def write_pack_file(slug: str, pack: dict[str, Any]) -> None:
    config.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = pack_path(slug).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    # Atomic swap: a reader must never catch a half-written pack, and the
    # background audio job rewrites this file while the feed is being served.
    tmp.replace(pack_path(slug))


@lru_cache(maxsize=32)
def load_pack(topic: str) -> dict[str, Any]:
    path = config.TOPICS_DIR / "{}.json".format(topic)
    if not path.exists():
        raise TopicNotFound(
            "no pack for {!r}. Run: python -m tools.generate_content".format(topic)
        )
    pack = json.loads(path.read_text(encoding="utf-8"))
    pack["clips"] = _clips()
    return pack


@lru_cache(maxsize=1)
def _clips() -> list[dict[str, Any]]:
    """The doomscroll reel. Manifest if present, else whatever is in clips/."""
    manifest = config.STATIC_DIR / "clips" / "manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))

    out = []
    for i, p in enumerate(sorted(config.CLIPS_DIR.glob("*.mp4"))):
        out.append(
            {
                "id": p.stem,
                "src": "/static/clips/{}".format(p.name),
                "caption": p.stem.replace("_", " "),
            }
        )
    return out


def list_topics() -> list[dict[str, Any]]:
    out = []
    for p in sorted(config.TOPICS_DIR.glob("*.json")):
        try:
            pack = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append(
            {
                "slug": p.stem,
                "title": pack.get("title", p.stem),
                "blurb": pack.get("blurb", ""),
                "emoji": pack.get("emoji", "*"),
                "item_count": len(pack.get("items", [])),
            }
        )
    return out


def clear_cache() -> None:
    """Called after regeneration so a running server picks up new packs."""
    load_pack.cache_clear()
    _clips.cache_clear()
