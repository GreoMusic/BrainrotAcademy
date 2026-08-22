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
import hashlib
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
def gen_items(topic: str, meta: dict) -> tuple[list[dict], list[dict]]:
    """Study items and their quiz questions, in one call.

    Generating the quiz separately meant a second round-trip that could not
    start until the items came back - the single biggest chunk of the wait on a
    cold topic. Asking for both together also removes the need for the model to
    echo item ids correctly, since each question is paired to its item by
    position here.
    """
    out = mc.chat_json(
        "Topic: {} ({}).\n\n"
        "Produce study material for a Gen-Z learning app that looks like TikTok.\n"
        'Return JSON: {{"flashcards":[{{"front":str,"back":str,"hook":str,'
        '"quiz":{{"q":str,"options":[str,str,str],"correct":int,"explain":str}}}}],'
        '"fun_facts":[{{"text":str,"emoji":str,'
        '"quiz":{{"q":str,"options":[str,str,str],"correct":int,"explain":str}}}}]}}\n'
        "- exactly {} flashcards and {} fun facts, each with its own quiz\n"
        "- 'front' is a real question, 'back' is under 20 words, 'hook' is a "
        "punchy 6-word teaser shown before the answer flips\n"
        "- fun facts must be genuinely surprising, one sentence, no preamble\n"
        "- each quiz tests THAT item; 'correct' is the 0-based index into "
        "options, wrong options must be plausible rather than jokes, and "
        "'explain' is one sentence shown after answering\n"
        "- vary which index is correct; do not always use 0\n"
        "- voice: casual and funny, but the facts must be correct\n"
        "- do not number them or repeat the topic name in every line".format(
            meta["title"], meta["blurb"], N_FLASHCARDS, N_FUN_FACTS
        ),
        system="You write addictive, accurate microlearning content. Output JSON only.",
        temperature=0.8,
    )

    items: list[dict] = []
    quiz: list[dict] = []

    def add_quiz(item_id: str, raw: dict | None) -> None:
        if not raw or len(raw.get("options", [])) < 2:
            return
        quiz.append(
            {
                "item_id": item_id,
                "q": raw["q"],
                "options": raw["options"],
                "correct": max(0, min(int(raw.get("correct", 0)), len(raw["options"]) - 1)),
                "explain": raw.get("explain", ""),
            }
        )

    for i, fc in enumerate(out.get("flashcards", [])[:N_FLASHCARDS]):
        item_id = "fc{}".format(i + 1)
        items.append(
            {
                "id": item_id,
                "kind": "flashcard",
                "front": fc["front"],
                "back": fc["back"],
                "hook": fc.get("hook", ""),
            }
        )
        add_quiz(item_id, fc.get("quiz"))

    for i, ff in enumerate(out.get("fun_facts", [])[:N_FUN_FACTS]):
        item_id = "ff{}".format(i + 1)
        items.append(
            {
                "id": item_id,
                "kind": "fun_fact",
                "text": ff["text"],
                "emoji": ff.get("emoji", "✨"),
            }
        )
        add_quiz(item_id, ff.get("quiz"))

    return items, quiz


def gen_podcast_script(topic: str, meta: dict) -> dict:
    """Two hosts, segmented. Host B is the skeptic, not a second narrator."""
    return mc.chat_json(
        "Topic: {} ({}).\n\n"
        "Write a two-host podcast that teaches this topic.\n"
        'Return JSON: {{"segments":[{{"id":"s1","title":str,'
        '"turns":[{{"speaker":"a"|"b","emotion":str,"text":str}}],'
        '"quiz_after":{{"q":str,"options":[str,str,str],"correct":int,'
        '"reaction_correct":str,"reaction_wrong":str}}}}]}}\n'
        "- exactly {} segments, each 4-6 turns, each segment under 110 words TOTAL\n"
        "- every turn needs an 'emotion' chosen for how the line is DELIVERED:\n"
        "    host a (the explainer): neutral, curious, excited, confident, cheerful\n"
        "    host b (the skeptic):   neutral, curious, confused, sarcasm, confident\n"
        "  use b's confused or curious for the dumb question, and sarcasm for a "
        "deadpan reaction. Do NOT leave every turn neutral.\n"
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
def _voice_for(speaker: str, emotion: str | None = None) -> str:
    """Cast one line.

    Preset voices are <family>_<emotion> slugs, and asking a family for an
    emotion it does not carry is a hard 404, so anything unrecognised falls
    back to neutral rather than failing the whole render.
    """
    family = config.VOICE_HOST_A if speaker == "a" else config.VOICE_HOST_B
    mood = (emotion or "").strip().lower()
    if mood not in config.VOICE_EMOTIONS.get(family, set()):
        mood = config.DEFAULT_EMOTION
    return "{}_{}".format(family, mood)


def _stem(turn_id: str, text: str, voice: str) -> str:
    """Filename for one rendered line.

    The content hash is what makes the resume-cache safe. Keyed on position
    alone, a regenerated script would find s1_t1.mp3 already on disk and ship
    the PREVIOUS take against the new line - stale audio, silently.
    """
    digest = hashlib.sha1("{}|{}".format(voice, text).encode("utf-8")).hexdigest()[:8]
    return "{}_{}".format(turn_id, digest)


def _duration(path: Path) -> float:
    try:
        from mutagen import File as MutagenFile

        mf = MutagenFile(path)
        return round(float(mf.info.length), 2) if mf and mf.info else 0.0
    except Exception:
        return 0.0


def render_audio(topic: str, script: dict, *, workers: int = 8, quiet: bool = False) -> dict:
    """Render every turn (and both quiz reactions) to its own MP3."""
    out_dir = config.AUDIO_DIR / topic
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[Path, str, str]] = []  # (path, text, voice_slug)

    for seg in script.get("segments", []):
        for ti, turn in enumerate(seg.get("turns", [])):
            turn["id"] = "{}_t{}".format(seg["id"], ti + 1)
            turn["voice"] = _voice_for(turn.get("speaker", "a"), turn.get("emotion"))
            stem = _stem(turn["id"], turn["text"], turn["voice"])
            path = out_dir / "{}.mp3".format(stem)
            turn["audio"] = "/static/audio/{}/{}.mp3".format(topic, stem)
            jobs.append((path, turn["text"], turn["voice"]))

        qa = seg.get("quiz_after")
        if qa:
            # Pre-render BOTH branches so the reaction is instant at demo time
            # instead of a two-second dead-air TTS wait.
            for key, suffix, mood in (
                ("reaction_correct", "ok", "confident"),
                ("reaction_wrong", "no", "sarcasm"),
            ):
                text = qa.get(key)
                if not text:
                    continue
                voice = _voice_for("b", mood)
                stem = _stem("{}_r{}".format(seg["id"], suffix), text, voice)
                path = out_dir / "{}.mp3".format(stem)
                qa["{}_audio".format(key)] = "/static/audio/{}/{}.mp3".format(topic, stem)
                jobs.append((path, text, voice))

    def render(job):
        path, text, voice = job
        if path.exists() and path.stat().st_size > 0:
            return path, True  # resume: never re-pay for audio already on disk
        path.write_bytes(mc.tts(text, voice_id=voice))
        return path, False

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, cached in pool.map(render, jobs):
            done += 1
            if not quiet:
                print("  [{}/{}] {}{}".format(
                    done, len(jobs), path.name, " (cached)" if cached else ""))

    # Durations let the UI size the progress dots and preload turn N+1.
    for seg in script.get("segments", []):
        for turn in seg.get("turns", []):
            # Derive from the url, not the turn id - the filename carries a
            # content hash now, so rebuilding it from the id would miss.
            turn["dur"] = _duration(out_dir / Path(turn["audio"]).name)
        seg["dur"] = round(sum(t.get("dur", 0) for t in seg.get("turns", [])), 2)

    return script


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def gen_meta(topic_text: str) -> dict:
    """Turn whatever the user typed into a presentable subject.

    Users type "ww2", "how do black holes work?", "kreb cycle" - none of which
    are titles. Also screens out prompts that are not a learning topic at all.
    """
    out = mc.chat_json(
        'A user typed this into a learning app: "{}"\n\n'
        'Return {{"ok":bool,"title":str,"emoji":str,"blurb":str,"reason":str}}\n'
        "- 'ok' is false only if this is not a teachable subject (abuse, "
        "nonsense, or a request for something other than learning)\n"
        "- 'title' is the tidy subject name, max 4 words, properly capitalised\n"
        "- 'emoji' is ONE emoji for it\n"
        "- 'blurb' is a punchy 8-word description of what they will learn\n"
        "- 'reason' explains the refusal, one friendly sentence, only when ok "
        "is false".format(topic_text[:200]),
        system="You normalise learning topics. Output JSON only.",
        temperature=0.3,
    )
    return out


def build_topic(
    topic: str, meta: dict | None = None, *, skip_audio: bool = False, quiet: bool = False
) -> dict:
    """Generate a full pack. `meta` defaults to the built-in demo topics.

    The two independent calls (study items and the podcast script) run
    concurrently; the quiz has to wait because it is keyed to the item ids.
    """
    meta = meta or TOPICS[topic]

    def log(msg):
        if not quiet:
            print(msg)

    log("\n=== {} ===".format(meta["title"]))
    log("- items + quiz + podcast script (parallel)...")

    # The only two text calls left, and they are independent of each other.
    with ThreadPoolExecutor(max_workers=2) as pool:
        items_f = pool.submit(gen_items, topic, meta)
        script_f = pool.submit(gen_podcast_script, topic, meta)
        items, quiz = items_f.result()
        script = script_f.result()

    n_turns = sum(len(s.get("turns", [])) for s in script.get("segments", []))
    log("  {} items | {} questions | {} segments / {} turns".format(
        len(items), len(quiz), len(script.get("segments", [])), n_turns))

    if skip_audio:
        log("- audio SKIPPED")
    else:
        log("- rendering audio...")
        script = render_audio(topic, script, quiet=quiet)

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
        "audio_ready": not skip_audio,
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

    todo = sorted(TOPICS) if args.all else ([args.topic] if args.topic else [])
    if not todo:
        ap.error("pass --topic, --all, --stub, or --list")

    for topic in todo:
        write_pack(build_topic(topic, skip_audio=args.skip_audio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
