"""Offline content generator. Run BEFORE the demo, never during it.

    python -m tools.generate_content --list
    python -m tools.generate_content --stub              # no API key needed
    python -m tools.generate_content --topic photosynthesis
    python -m tools.generate_content --all

Emits per topic: flashcards, fun facts, a quiz bank, a coach prompt, and a
two-host podcast rendered to one MP3 per turn.

Per-turn rendering (rather than one file per segment) is what buys the
interactivity: it gives clean pause boundaries, lets a live-generated answer be
spliced in mid-stream, and drives captions without word-level timestamps.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import mistral_client as mc  # noqa: E402

TOPICS = {
    "photosynthesis": {
        "title": "Photosynthesis",
        "emoji": "\U0001F331",
        "blurb": "How plants eat sunlight and air.",
    },
    "french-revolution": {
        "title": "The French Revolution",
        "emoji": "\U0001F5FC",
        "blurb": "How France went from king to chaos in a decade.",
    },
    "how-https-works": {
        "title": "How HTTPS Works",
        "emoji": "\U0001F510",
        "blurb": "Why the padlock means anything at all.",
    },
}

N_FLASHCARDS = 6
N_FUN_FACTS = 3
N_SEGMENTS = 4


# ---------------------------------------------------------------------------
# generation steps
# ---------------------------------------------------------------------------
def gen_items(topic: str, meta: dict) -> list[dict]:
    """Flashcards + fun facts, as one call so they do not overlap."""
    out = mc.chat_json(
        "Topic: {} ({}).\n\n"
        "Produce study material for a Gen-Z learning app that looks like TikTok.\n"
        "Return JSON: {{\"flashcards\":[{{\"front\":str,\"back\":str,\"hook\":str}}],"
        "\"fun_facts\":[{{\"text\":str,\"emoji\":str}}]}}\n"
        "- exactly {} flashcards and {} fun facts\n"
        "- 'front' is a real question, 'back' is under 20 words, 'hook' is a "
        "punchy 6-word teaser shown before the answer flips\n"
        "- fun facts must be genuinely surprising, one sentence, no preamble\n"
        "- voice: casual and funny, but the facts must be correct\n"
        "- do not number them or repeat the topic name in every line".format(
            meta["title"], meta["blurb"], N_FLASHCARDS, N_FUN_FACTS
        ),
        system="You write addictive, accurate microlearning content. Output JSON only.",
        temperature=0.8,
    )

    items: list[dict] = []
    for i, fc in enumerate(out.get("flashcards", [])[:N_FLASHCARDS]):
        items.append(
            {
                "id": "fc{}".format(i + 1),
                "kind": "flashcard",
                "front": fc["front"],
                "back": fc["back"],
                "hook": fc.get("hook", ""),
            }
        )
    for i, ff in enumerate(out.get("fun_facts", [])[:N_FUN_FACTS]):
        items.append(
            {
                "id": "ff{}".format(i + 1),
                "kind": "fun_fact",
                "text": ff["text"],
                "emoji": ff.get("emoji", "✨"),
            }
        )
    return items


def gen_quiz(topic: str, meta: dict, items: list[dict]) -> list[dict]:
    """One multiple-choice question per item, keyed by item id."""
    quizzable = [i for i in items if i["kind"] in ("flashcard", "fun_fact")]
    catalogue = "\n".join(
        "{}: {}".format(
            i["id"], i.get("front") or i.get("text", "")
        )
        for i in quizzable
    )
    out = mc.chat_json(
        "Topic: {}.\n\nWrite one multiple-choice question per item below.\n\n{}\n\n"
        'Return JSON: {{"quiz":[{{"item_id":str,"q":str,"options":[str,str,str],'
        '"correct":int,"explain":str}}]}}\n'
        "- 'correct' is the 0-based index into options\n"
        "- wrong options must be plausible, not jokes\n"
        "- 'explain' is one sentence shown after answering\n"
        "- vary which index is correct; do not always use 0\n"
        "- use the exact item_id strings given".format(meta["title"], catalogue),
        system="You write fair, unambiguous quiz questions. Output JSON only.",
        temperature=0.5,
    )

    valid = {i["id"] for i in quizzable}
    quiz = []
    for q in out.get("quiz", []):
        if q.get("item_id") in valid and len(q.get("options", [])) >= 2:
            q["correct"] = max(0, min(int(q.get("correct", 0)), len(q["options"]) - 1))
            quiz.append(q)
    return quiz


def gen_podcast_script(topic: str, meta: dict) -> dict:
    """Two hosts, segmented. Host B is the skeptic, not a second narrator."""
    return mc.chat_json(
        "Topic: {} ({}).\n\n"
        "Write a two-host podcast that teaches this topic.\n"
        'Return JSON: {{"segments":[{{"id":"s1","title":str,'
        '"turns":[{{"speaker":"a"|"b","text":str}}],'
        '"quiz_after":{{"q":str,"options":[str,str,str],"correct":int,'
        '"reaction_correct":str,"reaction_wrong":str}}}}]}}\n'
        "- exactly {} segments, each 4-6 turns, each segment under 110 words TOTAL\n"
        "- host a explains; host b is the skeptic who asks the dumb question the "
        "listener is actually thinking. Do NOT make b a second narrator.\n"
        "- they interrupt and react to each other; this is a conversation, not "
        "two monologues\n"
        "- no speaker labels, greetings, or sign-offs inside the text\n"
        "- 'reaction_correct' and 'reaction_wrong' are one short line from host b "
        "reacting to the listener's answer; keep them under 15 words\n"
        "- write for the ear: contractions, short sentences, no bullet points".format(
            meta["title"], meta["blurb"], N_SEGMENTS
        ),
        system="You write conversational audio scripts. Output JSON only.",
        temperature=0.85,
    )


# ---------------------------------------------------------------------------
# audio rendering
# ---------------------------------------------------------------------------
def _voice_for(speaker: str) -> str:
    return config.VOICE_HOST_A if speaker == "a" else config.VOICE_HOST_B


def _duration(path: Path) -> float:
    try:
        from mutagen import File as MutagenFile

        mf = MutagenFile(path)
        return round(float(mf.info.length), 2) if mf and mf.info else 0.0
    except Exception:
        return 0.0


def render_audio(topic: str, script: dict, *, workers: int = 8, force: bool = False) -> dict:
    """Render every turn (and both quiz reactions) to its own MP3."""
    out_dir = config.AUDIO_DIR / topic
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[Path, str, str]] = []  # (path, text, speaker)

    for seg in script.get("segments", []):
        for ti, turn in enumerate(seg.get("turns", [])):
            turn["id"] = "{}_t{}".format(seg["id"], ti + 1)
            path = out_dir / "{}.mp3".format(turn["id"])
            turn["audio"] = "/static/audio/{}/{}.mp3".format(topic, turn["id"])
            jobs.append((path, turn["text"], turn.get("speaker", "a")))

        qa = seg.get("quiz_after")
        if qa:
            # Pre-render BOTH branches so the reaction is instant at demo time
            # instead of a two-second dead-air TTS wait.
            for key, suffix in (("reaction_correct", "ok"), ("reaction_wrong", "no")):
                text = qa.get(key)
                if not text:
                    continue
                name = "{}_r{}".format(seg["id"], suffix)
                path = out_dir / "{}.mp3".format(name)
                qa["{}_audio".format(key)] = "/static/audio/{}/{}.mp3".format(topic, name)
                jobs.append((path, text, "b"))

    def render(job):
        path, text, speaker = job
        if not force and path.exists() and path.stat().st_size > 0:
            return path, True  # resume: never re-pay for audio already on disk
        path.write_bytes(mc.tts(text, voice_id=_voice_for(speaker)))
        return path, False

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, cached in pool.map(render, jobs):
            done += 1
            print("  [{}/{}] {}{}".format(done, len(jobs), path.name, " (cached)" if cached else ""))

    # Durations let the UI size the progress dots and preload turn N+1.
    for seg in script.get("segments", []):
        for turn in seg.get("turns", []):
            turn["dur"] = _duration(out_dir / "{}.mp3".format(turn["id"]))
        seg["dur"] = round(sum(t.get("dur", 0) for t in seg.get("turns", [])), 2)

    return script


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def build_topic(topic: str, *, skip_audio: bool = False) -> dict:
    meta = TOPICS[topic]
    print("\n=== {} ===".format(meta["title"]))

    print("- items...")
    items = gen_items(topic, meta)
    print("  {} items".format(len(items)))

    print("- quiz...")
    quiz = gen_quiz(topic, meta, items)
    print("  {} questions".format(len(quiz)))

    print("- podcast script...")
    script = gen_podcast_script(topic, meta)
    n_turns = sum(len(s.get("turns", [])) for s in script.get("segments", []))
    print("  {} segments / {} turns".format(len(script.get("segments", [])), n_turns))

    if skip_audio:
        print("- audio SKIPPED")
    else:
        print("- rendering audio...")
        script = render_audio(topic, script)

    # Podcast segments enter the feed as ordinary LEARN items.
    for seg in script.get("segments", []):
        items.append(
            {
                "id": "pod_{}".format(seg["id"]),
                "kind": "podcast",
                "segment_id": seg["id"],
                "title": seg.get("title", ""),
            }
        )

    return {
        "topic": topic,
        "title": meta["title"],
        "emoji": meta["emoji"],
        "blurb": meta["blurb"],
        "items": items,
        "quiz": quiz,
        "podcast": script,
        "coach_system": (
            "You are a warm, sharp tutor quizzing someone on {}. Ask ONE short "
            "question at a time and react to their answer honestly - correct them "
            "when they are wrong. Keep every reply under 40 words and sound like a "
            "person, not a textbook.".format(meta["title"])
        ),
    }


def write_pack(pack: dict) -> Path:
    config.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TOPICS_DIR / "{}.json".format(pack["topic"])
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote {} ({:.1f} KB)".format(path, path.stat().st_size / 1024))
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", choices=sorted(TOPICS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stub", action="store_true", help="hand-written pack, no API calls")
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument(
        "--rerender-audio",
        action="store_true",
        help="replace podcast MP3s in an existing topic pack using current voices",
    )
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for slug, meta in sorted(TOPICS.items()):
            print("{:20} {}".format(slug, meta["title"]))
        return 0

    if args.stub:
        from tools.stub_pack import STUB

        write_pack(STUB)
        print("\nStub pack written - the feed works now, without an API key.")
        return 0

    if args.rerender_audio:
        if not args.topic:
            ap.error("--rerender-audio requires --topic")
        path = config.TOPICS_DIR / "{}.json".format(args.topic)
        if not path.exists():
            ap.error("topic pack does not exist: {}".format(path))
        pack = json.loads(path.read_text(encoding="utf-8"))
        pack["podcast"] = render_audio(args.topic, pack["podcast"], force=True)
        write_pack(pack)
        return 0

    todo = sorted(TOPICS) if args.all else ([args.topic] if args.topic else [])
    if not todo:
        ap.error("pass --topic, --all, --stub, --rerender-audio, or --list")

    for topic in todo:
        write_pack(build_topic(topic, skip_audio=args.skip_audio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
