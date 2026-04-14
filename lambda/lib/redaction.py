"""PII span parsing and index-safe placeholder redaction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntitySpan:
    start: int
    end: int
    entity_type: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Invalid span: {self}")


def placeholder_for(entity_type: str) -> str:
    t = entity_type.upper()
    mapping = {
        "PERSON": "[NAME]",
        "PER": "[NAME]",
        "NAME": "[NAME]",
        "SSN": "[SSN]",
        "EMAIL": "[EMAIL]",
        "PHONE": "[PHONE]",
        "TEL": "[PHONE]",
        "ADDRESS": "[ADDRESS]",
        "LOC": "[ADDRESS]",
        "CREDIT_CARD": "[CREDIT_CARD]",
        "CARD": "[CREDIT_CARD]",
    }
    return mapping.get(t, f"[{t}]")


def parse_entities(model_output: dict[str, Any]) -> list[EntitySpan]:
    """
    Expects model JSON like:
    {"entities": [{"start": 0, "end": 8, "type": "NAME"}, ...]}
    """
    entities: list[EntitySpan] = []
    for item in model_output.get("entities", []):
        entities.append(
            EntitySpan(
                start=int(item["start"]),
                end=int(item["end"]),
                entity_type=str(item.get("type", "PII")),
            )
        )
    return entities


def redact_index_safe(text: str, entities: list[EntitySpan]) -> str:
    """
    Replace from highest start index first so UTF-8 code unit offsets stay valid.
    Skips spans that overlap an already-replaced region (closer to end of string).
    """
    sorted_spans = sorted(entities, key=lambda e: (e.start, e.end), reverse=True)
    out = text
    last_start = len(out)

    for span in sorted_spans:
        if span.end > last_start:
            logger.warning("Skipping overlapping span %s", span)
            continue
        ph = placeholder_for(span.entity_type)
        out = out[: span.start] + ph + out[span.end :]
        last_start = span.start

    return out
