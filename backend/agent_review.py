from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .query_engine import answer_question_events, send_email


def executive_review_events(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream the prompt-driven query engine without imposing an analysis recipe."""
    yield from answer_question_events(question, history, stream_content=True)
