"""Make resilient source failures explicit without turning missing data into facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class SourceOutcome(Generic[T]):
    source: str
    value: T
    error_type: str | None = None

    def event(self, *, available: bool, source: str | None = None) -> dict[str, str]:
        event = {
            "source": source or self.source,
            "status": "source_error" if self.error_type else ("ok" if available else "unavailable"),
        }
        if self.error_type:
            event["error_type"] = self.error_type
        return event


def capture_source(source: str, fetch: Callable[[], T], fallback: T | Callable[[Exception], T]) -> SourceOutcome[T]:
    try:
        return SourceOutcome(source=source, value=fetch())
    except Exception as exc:
        value = fallback(exc) if callable(fallback) else fallback
        return SourceOutcome(source=source, value=value, error_type=type(exc).__name__)
