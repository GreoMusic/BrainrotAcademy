"""Hour-1 gate: prove all three Mistral surfaces work before building on them.

    python -m tools.smoke_test

Also prints the real preset voice ids so config.py can stop guessing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import mistral_client as mc  # noqa: E402

OK, FAIL = "[ OK ]", "[FAIL]"


def main() -> int:
    failures = []

    # 1. preset voices -- also tells us what to put in config.
    voice_a = config.VOICE_HOST_A
    try:
        voices = mc.list_preset_voices()
        print(f"{OK} voices.list -> {len(voices)} preset voices")
        for v in voices:
            print(f"       id={v['id']!r:28} name={v['name']!r:16} gender={v['gender']}")
        if voices:
            voice_a = voices[0]["id"]
    except Exception as exc:
        print(f"{FAIL} voices.list: {exc}")
        failures.append("voices")

    # 2. chat + JSON mode
    try:
        got = mc.chat_json(
            'Return exactly {"ping":"pong","n":42} and nothing else.',
            temperature=0,
        )
        assert got.get("ping") == "pong", got
        print(f"{OK} chat_json -> {got}")
    except Exception as exc:
        print(f"{FAIL} chat_json: {exc}")
        failures.append("chat")

    # 3. TTS round-trip
    audio = None
    try:
        audio = mc.tts("Plants are basically solar panels that eat air.", voice_id=voice_a)
        out = config.STATIC_DIR / "audio" / "_smoke.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        print(f"{OK} tts -> {len(audio)} bytes, wrote {out}")
    except Exception as exc:
        print(f"{FAIL} tts: {exc}")
        failures.append("tts")

    # 4. STT round-trip -- feed our own TTS output straight back in.
    if audio:
        try:
            text = mc.transcribe(audio, filename="_smoke.mp3")
            print(f"{OK} transcribe -> {text!r}")
        except Exception as exc:
            print(f"{FAIL} transcribe: {exc}")
            failures.append("stt")
    else:
        print("[skip] transcribe (no audio from tts)")

    print()
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("All Mistral surfaces green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
