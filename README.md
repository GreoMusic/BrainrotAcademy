## Brainrot Academy

**"You don't get in the club until you prove you've got something upstairs."**

Brainrot Academy is an app that gates mindless doomscrolling behind proof of real learning — turning brainrot consumption into a reward you have to earn, not a default state you fall into.

### The Loop

1. **Learn** — Mistral dynamically generates bite-sized learning content on a topic: an interactive podcast, flashcards, and fun facts, so every session feels fresh instead of reused material.
2. **Prove it** — An AI conversational coach quizzes you, talking through what you just learned like a real study partner. Mistral judges whether your answers show genuine understanding or you're just bluffing. Fail, and you're sent back to the learning stage. Pass, and the gate opens.
3. **Scroll (briefly)** — Once you're "worthy," you get timed access to a TikTok-style feed — same addictive scroll mechanic, but built on static/curated content instead of an infinite algorithmic pit.
4. **Hit friction** — Just as you settle in, the app throws up a wall: solve a quick math problem, or go talk to a real person nearby (with live transcription) before you can keep scrolling.
5. **Back to learning** — The loop resets, pulling you back toward learning instead of letting the scroll spiral continue.

### Why It Works

Instead of just blocking brainrot (which people route around), BrainrotBouncer makes the *price of admission* real cognitive or social effort — verified by AI, not an honor system. The scrolling itself is never removed; it's just no longer free.

### Stack

- **AI:** Mistral (content generation + learning verification) 
- **Backend:** Python / Flask 
- **Frontend:** Vue.js

---

## Run it

Two terminals.

```bash
cd backend && .venv/Scripts/python.exe -m flask --app app run --port 5001
```

```bash
cd frontend && npm run dev
```

Open http://localhost:5173.

## First-time setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m tools.generate_content --stub
```

`--stub` writes a hand-written photosynthesis pack, so **the whole feed works
without an API key**. Add a key only when you want generated topics and audio.

```bash
cp .env.example .env      # then put your key in it
.venv/Scripts/python.exe -m tools.smoke_test          # verifies chat + TTS + STT
.venv/Scripts/python.exe -m tools.generate_content --all
```

Drop any vertical `.mp4` files into `backend/static/clips/` and they become the
doomscroll reel automatically.

## Tests

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
```

`test_orchestrator.py` drives the transition engine directly — no server, no
network. `test_api.py` proves the HTTP wiring. If the first is green, the core
of the app works and any bug is in the wiring.

## How it fits together

| File | Role |
|---|---|
| `backend/orchestrator.py` | The transition engine. Pure functions over a dict. |
| `backend/routes/session.py` | The feed's only critical path. Does no network I/O. |
| `backend/mistral_client.py` | Every Mistral call: chat, vision, TTS, transcription. |
| `backend/tools/generate_content.py` | Offline. Writes topic packs + podcast MP3s. |
| `frontend/src/views/FeedView.vue` | Scroll-snap feed, server-driven card switch. |
| `frontend/src/components/cards/` | One component per card type. |

### Two rules worth not breaking

**Nothing on the scroll path calls an API.** Every card served by
`/api/session/<id>/next` comes from a pre-generated pack on disk. That is why
the feed survives bad wifi, and why generation is a separate offline step.

**Prefetch stops at a blocking card.** Quiz cards and friction gates end the
batch (`BLOCKING` in `routes/session.py`). Serving past one would advance
session state for a card the client never shows, silently skipping questions.

### Gates block by being last

A friction gate stops the feed simply by being the final card, since the client
will not fetch more until it is cleared. There is no scroll-locking anywhere.

## Mistral surface

| Job | Model |
|---|---|
| Flashcards, quizzes, podcast scripts, coach, grading | `mistral-medium-latest` |
| Touch-grass photo check | `mistral-medium-latest` (vision) |
| Podcast + coach speech | `voxtral-mini-tts-latest` |
| Coach mic + conversation check | `voxtral-mini-transcribe-latest` |

SDK note: on `mistralai` 2.x the import is `from mistralai.client import Mistral`,
and `audio.speech.complete(...)` returns `audio_data` as a **base64 string**.
Preset voices exist — `audio.voices.list(type_="preset")` — so no voice cloning
setup is required.
