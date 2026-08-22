## Brainrot Academy

**"You don't get in the club until you prove you've got something upstairs."**

Brainrot Academy is an app that gates mindless doomscrolling behind proof of real learning — turning brainrot consumption into a reward you have to earn, not a default state you fall into.

### The Loop

1. **Learn** — Mistral dynamically generates bite-sized learning content on a topic: an interactive podcast, flashcards, and fun facts, so every session feels fresh instead of reused material.
2. **Prove it** — An AI conversational coach quizzes you, talking through what you just learned like a real study partner. Mistral judges whether your answers show genuine understanding or you're just bluffing. Fail, and you're sent back to the learning stage. Pass, and the gate opens.
3. **Scroll (briefly)** — Once you're "worthy," you get timed access to a TikTok-style feed — same addictive scroll mechanic, but built on static/curated content instead of an infinite algorithmic pit.
4. **Hit friction** — Just as you settle in, the app throws up a wall: solve a math problem (and photograph your actual work — a correct number alone proves nothing) or go talk to a real person nearby (with live transcription) before you can keep scrolling.
5. **Scroll again** — Clearing that first wall buys one more round of scroll, not an instant trip back to lessons.
6. **Hit friction again, then back to learning** — The second wall in a row resets the loop, pulling you back toward learning instead of letting the scroll spiral continue indefinitely.

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
cd backend && .venv/bin/python -m flask --app app run --port 5001
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
cp .env.example .env      # then put your Mistral (and optionally GIPHY) key in it
.venv/Scripts/python.exe -m tools.smoke_test
```

`smoke_test` verifies chat, TTS and transcription in one shot and prints the
real preset voice ids. Everything else is generated on demand.

The doomscroll reel is built from two sources, interleaved: any vertical
`.mp4` files dropped into `backend/static/clips/`, and actual GIPHY brainrot
(skibidi, subway surfers, sigma, and the rest of `BRAINROT_QUERIES` in
`backend/giphy_client.py` — not generic trending, which skews toward normal
meme content) if `GIPHY_API_KEY` is set (free key at
https://developers.giphy.com/). Both are optional — with neither, the reel
falls back to a placeholder card. GIPHY clips are fetched once per topic at
generation time, same as the podcast audio, so nothing on the scroll path
ever calls an API.

### Topics are generated on demand

Type any subject at the gate and Mistral builds the round for it: flashcards,
fun facts, a quiz, and a two-host podcast. Packs are cached to
`backend/data/topics/`, so the same subject is instant next time.

Text takes ~12s on a cold topic and gates the feed behind a progress screen.
Audio is slower (~29 TTS clips), so it renders in a **background thread** and
the pack is rewritten when it lands; until then the podcast plays from captions
on a duration timer and shows a "voices rendering" badge. Two rules hold:

- **Nothing is generated mid-scroll.** Generation happens once per topic at
  session start. Once the feed is running it serves entirely from disk.
- **Rendered clips are named by content hash.** Keyed on turn position alone, a
  regenerated script would find `s1_t1.mp3` on disk and ship the previous take
  against the new line.

To pre-warm topics before a demo (optional):

```bash
cd backend && .venv/Scripts/python.exe -m tools.generate_content --all
```

`--stub` still writes a hand-authored photosynthesis pack with no API calls, as
an offline fallback.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
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
| `backend/giphy_client.py` | GIPHY reel clips. Best-effort - no key or a failure just means fewer clips. |
| `backend/tools/generate_content.py` | Offline. Writes topic packs + podcast MP3s + reel gifs. |
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
| Topic normalising, flashcards, quizzes, podcast scripts, coach, grading | `mistral-medium-latest` |
| Touch-grass / math-work photo checks | `mistral-medium-latest` (vision) |
| Podcast + coach speech | `voxtral-mini-tts-latest` |
| Talk-to-human transcription | `voxtral-mini-latest` |
| Live coach transcription | `voxtral-mini-transcribe-realtime-2602` |

Voices are presets from `audio.voices.list(type_="preset")`, which ship as
`<family>_<emotion>` slugs. A host is a voice family and each line picks an
emotion, so the skeptic can actually sound confused and then sarcastic — that
is most of what stops a two-hander sounding like one narrator reading both
parts. Asking a family for an emotion it lacks is a hard 404, hence the
fallback table in `config.py`.

SDK notes for `mistralai` 2.x, where the docs and the API disagree:

- the import is `from mistralai.client import Mistral`, not `from mistralai import …`
- `audio.speech.complete(...)` returns `audio_data` as a **base64 string**
- `voices.list(...)` paginates under `items` — there is no `voices` or `data`
- the documented `voxtral-mini-transcribe-*` ids are **not served**; the general
  `voxtral-mini-latest` handles the transcriptions endpoint
