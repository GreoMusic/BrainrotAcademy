import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from tools import generate_content  # noqa: E402


def test_one_rejected_turn_does_not_cancel_podcast_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)

    def fake_tts(text, *, voice_id):
        if "blocked" in text:
            raise RuntimeError("guardrail rejection")
        return b"valid mp3 bytes"

    monkeypatch.setattr(generate_content.mc, "tts", fake_tts)
    script = {
        "segments": [
            {
                "id": "s1",
                "turns": [
                    {"speaker": "a", "text": "A safe line."},
                    {"speaker": "b", "text": "A blocked line."},
                ],
            }
        ]
    }

    rendered = generate_content.render_audio("test-topic", script, workers=2, quiet=True)
    safe, blocked = rendered["segments"][0]["turns"]

    assert safe["audio"].endswith(".mp3")
    assert (tmp_path / "test-topic" / Path(safe["audio"]).name).exists()
    assert "audio" not in blocked
    assert blocked["dur"] >= 3
