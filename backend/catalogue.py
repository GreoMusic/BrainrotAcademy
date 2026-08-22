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
            {"slug": "grammar-and-punctuation", "title": "Grammar & Punctuation"},
            {"slug": "rhetorical-devices", "title": "Rhetorical Devices"},
            {"slug": "etymology", "title": "Etymology"},
            {"slug": "poetic-meter", "title": "Poetic Meter"},
            {"slug": "narrative-perspective", "title": "Narrative Perspective"},
        ],
    },
    {
        "slug": "science",
        "title": "Science",
        "emoji": "\U0001F9EA",
        "topics": [
            {"slug": "photosynthesis", "title": "Photosynthesis"},
            {"slug": "plate-tectonics", "title": "Plate Tectonics"},
            {"slug": "the-krebs-cycle", "title": "The Krebs Cycle"},
            {"slug": "black-holes", "title": "Black Holes"},
            {"slug": "crispr", "title": "CRISPR"},
            {"slug": "entropy", "title": "Entropy"},
        ],
    },
    {
        "slug": "math",
        "title": "Math",
        "emoji": "\U0001F4D0",
        "topics": [
            {"slug": "bayes-theorem", "title": "Bayes' Theorem"},
            {"slug": "modular-arithmetic", "title": "Modular Arithmetic"},
            {"slug": "eigenvectors", "title": "Eigenvectors"},
            {"slug": "the-central-limit-theorem", "title": "The Central Limit Theorem"},
            {"slug": "graph-theory", "title": "Graph Theory"},
        ],
    },
    {
        "slug": "engineering",
        "title": "Engineering",
        "emoji": "⚙️",
        "topics": [
            {"slug": "mechanical-comprehension", "title": "Mechanical Comprehension"},
            {"slug": "roman-concrete", "title": "Roman Concrete"},
            {"slug": "control-systems", "title": "Control Systems"},
            {"slug": "how-bridges-stand-up", "title": "How Bridges Stand Up"},
            {"slug": "jet-engines", "title": "Jet Engines"},
        ],
    },
    {
        "slug": "coding",
        "title": "Coding",
        "emoji": "\U0001F4BB",
        "topics": [
            {"slug": "python", "title": "Python"},
            {"slug": "how-https-works", "title": "How HTTPS Works"},
            {"slug": "big-o-notation", "title": "Big-O Notation"},
            {"slug": "git-branching", "title": "Git Branching"},
            {"slug": "regular-expressions", "title": "Regular Expressions"},
            {"slug": "race-conditions", "title": "Race Conditions"},
        ],
    },
    {
        "slug": "history",
        "title": "History",
        "emoji": "\U0001F5FF",
        "topics": [
            {"slug": "the-french-revolution", "title": "The French Revolution"},
            {"slug": "the-silk-road", "title": "The Silk Road"},
            {"slug": "the-bronze-age-collapse", "title": "The Bronze Age Collapse"},
            {"slug": "the-space-race", "title": "The Space Race"},
            {"slug": "the-printing-press", "title": "The Printing Press"},
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
