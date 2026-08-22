"""Two-level topic catalogue, and the rule that you never repeat yourself.

Level one is a broad subject (Science, Coding); level two is something narrow
enough to actually teach in a round (Photosynthesis, Python).

Selecting a topic spends it. A spent topic cannot be picked again until every
topic in the catalogue has been spent, at which point the whole board resets
and a new cycle begins. Usage is written to disk, because "you already did
that one" is a claim that has to survive a restart to mean anything.
"""
from __future__ import annotations

import json
import threading
from typing import Any

import config

USAGE_PATH = config.DATA_DIR / "usage.json"

_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# the catalogue
# ---------------------------------------------------------------------------
# Slugs are explicit rather than derived, because they are the key that usage,
# cached packs and rendered audio all agree on. Deriving them from titles would
# let a wording tweak orphan a pack.
SUBJECTS: list[dict[str, Any]] = [
    {
        "slug": "english",
        "title": "English",
        "emoji": "\U0001F4DA",
        "topics": [
            {"slug": "technical-writing", "title": "Technical Writing"},
            {"slug": "clear-arguments", "title": "Clear Arguments"},
            {"slug": "rhetoric-and-persuasion", "title": "Rhetoric & Persuasion"},
            {"slug": "etymology", "title": "Etymology"},
            {"slug": "data-storytelling", "title": "Data Storytelling"},
            {"slug": "reading-research-papers", "title": "Reading Research Papers"},
        ],
    },
    {
        "slug": "science",
        "title": "Science",
        "emoji": "\U0001F9EA",
        "topics": [
            {"slug": "scientific-method", "title": "Scientific Method"},
            {"slug": "semiconductor-physics", "title": "Semiconductor Physics"},
            {"slug": "battery-chemistry", "title": "Battery Chemistry"},
            {"slug": "crispr", "title": "Genetics & CRISPR"},
            {"slug": "climate-systems", "title": "Climate Systems"},
            {"slug": "photosynthesis", "title": "Photosynthesis"},
        ],
    },
    {
        "slug": "math",
        "title": "Math",
        "emoji": "\U0001F4D0",
        "topics": [
            {"slug": "probability-and-statistics", "title": "Probability & Statistics"},
            {"slug": "bayesian-inference", "title": "Bayesian Inference"},
            {"slug": "linear-algebra", "title": "Linear Algebra"},
            {"slug": "graph-theory", "title": "Graph Theory"},
            {"slug": "optimization", "title": "Optimization"},
            {"slug": "queueing-theory", "title": "Queueing Theory"},
        ],
    },
    {
        "slug": "engineering",
        "title": "Engineering",
        "emoji": "⚙️",
        "topics": [
            {"slug": "systems-engineering", "title": "Systems Engineering"},
            {"slug": "control-systems", "title": "Control Systems"},
            {"slug": "reliability-engineering", "title": "Reliability Engineering"},
            {"slug": "semiconductor-manufacturing", "title": "Semiconductor Manufacturing"},
            {"slug": "robotics-and-automation", "title": "Robotics & Automation"},
            {"slug": "energy-systems", "title": "Energy Systems"},
        ],
    },
    {
        "slug": "coding",
        "title": "Coding",
        "emoji": "\U0001F4BB",
        "topics": [
            {"slug": "data-structures-and-algorithms", "title": "Data Structures & Algorithms"},
            {"slug": "distributed-systems", "title": "Distributed Systems"},
            {"slug": "database-internals", "title": "Database Internals"},
            {"slug": "networking-and-http", "title": "Networking & HTTP"},
            {"slug": "concurrency", "title": "Concurrency"},
            {"slug": "machine-learning-systems", "title": "Machine Learning Systems"},
        ],
    },
    {
        "slug": "history",
        "title": "History",
        "emoji": "\U0001F5FF",
        "topics": [
            {"slug": "history-of-computing", "title": "History of Computing"},
            {"slug": "history-of-the-internet", "title": "History of the Internet"},
            {"slug": "silicon-valley", "title": "Rise of Silicon Valley"},
            {"slug": "open-source-movement", "title": "Open-Source Movement"},
            {"slug": "the-space-race", "title": "The Space Race"},
            {"slug": "industrial-revolutions", "title": "Industrial Revolutions"},
        ],
    },
]

# slug -> {subject_slug, subject_title, emoji, title}
_INDEX: dict[str, dict[str, Any]] = {
    t["slug"]: {
        "slug": t["slug"],
        "title": t["title"],
        "subject": s["slug"],
        "subject_title": s["title"],
        "emoji": s["emoji"],
    }
    for s in SUBJECTS
    for t in s["topics"]
}

ALL_SLUGS = frozenset(_INDEX)


def lookup(slug: str) -> dict[str, Any] | None:
    return _INDEX.get(slug)


def find_by_title(title: str) -> dict[str, Any] | None:
    """Let free text land on a catalogue entry when it plainly means one."""
    want = (title or "").strip().lower()
    for entry in _INDEX.values():
        if entry["title"].lower() == want:
            return entry
    return None


# ---------------------------------------------------------------------------
# usage
# ---------------------------------------------------------------------------
def _read() -> dict[str, Any]:
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"used": [], "cycle": 1, "adhoc": []}
    data.setdefault("used", [])
    data.setdefault("cycle", 1)
    data.setdefault("adhoc", [])
    # Drop anything no longer in the catalogue, or a removed topic would keep
    # the board from ever reaching "exhausted".
    data["used"] = [s for s in data["used"] if s in ALL_SLUGS]
    return data


def _write(data: dict[str, Any]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = USAGE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(USAGE_PATH)


def state() -> dict[str, Any]:
    with _LOCK:
        return _read()


def is_used(slug: str) -> bool:
    return slug in set(state()["used"])


def remaining() -> list[str]:
    used = set(state()["used"])
    return [s for s in _INDEX if s not in used]


def mark_used(slug: str) -> dict[str, Any]:
    """Spend a topic. Resets the board if that was the last one.

    Returns {"cycle", "used", "total", "reset": bool}.
    """
    with _LOCK:
        data = _read()
        used = set(data["used"])

        if slug in ALL_SLUGS:
            used.add(slug)
        elif slug not in data["adhoc"]:
            # Typed topics are remembered for the UI but never gate the cycle -
            # otherwise the board could never be exhausted.
            data["adhoc"].append(slug)

        reset = False
        if used >= ALL_SLUGS:
            # Every topic spent: new cycle, whole board available again.
            used = set()
            data["cycle"] = int(data.get("cycle", 1)) + 1
            reset = True

        data["used"] = sorted(used)
        _write(data)
        return {
            "cycle": data["cycle"],
            "used": len(data["used"]),
            "total": len(ALL_SLUGS),
            "reset": reset,
        }


def reset(cycle_bump: bool = True) -> dict[str, Any]:
    with _LOCK:
        data = _read()
        data["used"] = []
        if cycle_bump:
            data["cycle"] = int(data.get("cycle", 1)) + 1
        _write(data)
        return data


# ---------------------------------------------------------------------------
# view for the picker
# ---------------------------------------------------------------------------
def browse() -> dict[str, Any]:
    """The whole board, with what is spent and what is left."""
    data = state()
    used = set(data["used"])

    subjects = []
    for s in SUBJECTS:
        topics = [
            {
                "slug": t["slug"],
                "title": t["title"],
                "used": t["slug"] in used,
                "cached": (config.TOPICS_DIR / "{}.json".format(t["slug"])).exists(),
            }
            for t in s["topics"]
        ]
        subjects.append(
            {
                "slug": s["slug"],
                "title": s["title"],
                "emoji": s["emoji"],
                "topics": topics,
                "used": sum(1 for t in topics if t["used"]),
                "total": len(topics),
            }
        )

    return {
        "subjects": subjects,
        "cycle": data["cycle"],
        "used": len(used),
        "total": len(ALL_SLUGS),
        "remaining": len(ALL_SLUGS) - len(used),
    }
