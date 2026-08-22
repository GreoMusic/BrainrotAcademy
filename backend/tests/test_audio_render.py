import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import content  # noqa: E402
import topics  # noqa: E402
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


def test_cached_pack_with_missing_mp3s_is_repaired(tmp_path, monkeypatch):
    topics_dir = tmp_path / "topics"
    static_dir = tmp_path / "static"
    topics_dir.mkdir()
    monkeypatch.setattr(config, "TOPICS_DIR", topics_dir)
    monkeypatch.setattr(config, "STATIC_DIR", static_dir)
    content.clear_cache()

    pack = {
        "topic": "missing-voices",
        "audio_ready": True,
        "podcast": {
            "segments": [
                {
                    "id": "s1",
                    "turns": [
                        {
                            "text": "This URL points at a file that does not exist.",
                            "audio": "/static/audio/missing-voices/s1.mp3",
                        }
                    ],
                }
            ]
        },
    }
    content.write_pack_file("missing-voices", pack)
    monkeypatch.setattr(topics, "_kick_audio", lambda _slug: None)

    _, repaired = topics.ensure_pack("Missing Voices", slug="missing-voices")

    assert repaired["audio_ready"] is False
    assert "audio" not in repaired["podcast"]["segments"][0]["turns"][0]
    content.clear_cache()
