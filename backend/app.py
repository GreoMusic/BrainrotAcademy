"""Flask app factory.

    ./.venv/Scripts/python.exe -m flask --app app run --debug --port 5001
"""
from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

import config


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app)

    from routes.session import bp as session_bp

    app.register_blueprint(session_bp)

    # Optional blueprints: these call Mistral live, so the feed must still boot
    # without them if a key is missing or a module is half-written.
    for module, name in (
        ("routes.coach", "coach"),
        ("routes.friction", "friction"),
    ):
        try:
            mod = __import__(module, fromlist=["bp"])
            app.register_blueprint(mod.bp)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("skipped %s blueprint: %s", name, exc)

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "has_key": bool(config.MISTRAL_API_KEY),
                "chat_model": config.CHAT_MODEL,
                "tts_model": config.TTS_MODEL,
                "stt_model": config.STT_MODEL,
            }
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(port=5001, debug=True)
