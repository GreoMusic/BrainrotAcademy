"""Focused tests for local Mistral response normalization."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mistral_client  # noqa: E402


def test_ocr_markdown_fallback_recognizes_a_standalone_number():
    assert mistral_client._answer_from_ocr_markdown("35") == "35"


def test_ocr_markdown_fallback_uses_the_last_written_number():
    assert mistral_client._answer_from_ocr_markdown("5 × 7\n35") == "35"


def test_ocr_markdown_fallback_ignores_image_asset_numbers():
    assert mistral_client._answer_from_ocr_markdown("![work](img-35.jpeg)") is None


def test_ocr_response_uses_page_text_when_annotation_is_null(monkeypatch):
    response = SimpleNamespace(
        document_annotation='{"final_answer": null}',
        pages=[SimpleNamespace(markdown="35")],
    )
    fake_client = SimpleNamespace(
        ocr=SimpleNamespace(process=lambda **_kwargs: response),
    )
    monkeypatch.setattr(mistral_client, "get_client", lambda: fake_client)

    result = mistral_client.ocr_math_answer(b"image", "5 x 7")

    assert result["final_answer"] == "35"
    assert result["markdown"] == "35"
