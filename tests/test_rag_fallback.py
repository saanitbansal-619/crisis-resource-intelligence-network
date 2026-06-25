"""Tests for hosted-mode / keyword RAG fallback behavior.

These tests must not require Ollama, pgvector, or live retrieval. They exercise
the keyword-fallback context builder with in-memory sample chunks.
"""

import pytest

# scikit-learn / sqlalchemy are imported transitively; skip cleanly if absent.
rag_briefing = pytest.importorskip("rag.rag_briefing")

from rag.rag_briefing import (  # noqa: E402
    KEYWORD_FALLBACK_NOTE,
    build_keyword_fallback_context,
)

SAMPLE_ZONE = {"zone_name": "Chad Sahel Transit Zone", "country": "Chad"}

SAMPLE_CHUNKS = [
    {
        "chunk_id": "c1",
        "title": "Chad humanitarian update",
        "country": "Chad",
        "event_type": "drought",
        "source_type": "reliefweb",
        "url": "https://example.org/report",
        "chunk_text": "Food and water needs are rising across displacement sites.",
        "is_fallback": False,
        "final_score": 0.82,
    }
]


def test_fallback_helper_importable_without_ollama() -> None:
    assert callable(build_keyword_fallback_context)


def test_fallback_reports_keyword_mode_with_sample_data() -> None:
    result = build_keyword_fallback_context(SAMPLE_ZONE, SAMPLE_CHUNKS)

    assert result["retrieval_mode"] == "keyword_fallback"
    assert result["is_fallback"] is True


def test_fallback_returns_sources_when_data_provided() -> None:
    result = build_keyword_fallback_context(SAMPLE_ZONE, SAMPLE_CHUNKS)

    sources = result["retrieved_context"]
    assert isinstance(sources, list)
    assert len(sources) == 1
    assert sources[0]["country"] == "Chad"


def test_fallback_summary_mentions_keyword_mode() -> None:
    result = build_keyword_fallback_context(SAMPLE_ZONE, SAMPLE_CHUNKS)
    assert KEYWORD_FALLBACK_NOTE in result["rag_summary"]


def test_fallback_clear_message_when_no_records() -> None:
    result = build_keyword_fallback_context(SAMPLE_ZONE, [])

    assert result["retrieved_context"] == []
    summary = result["rag_summary"]
    assert KEYWORD_FALLBACK_NOTE in summary
    assert "No matching" in summary
