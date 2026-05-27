from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Optional

from src.models.span import Span


@dataclass
class Trace:
    trace_id: str
    spans: list[Span]
    root_service: Optional[str] = None

    def __post_init__(self):
        if self.root_service is None:
            for span in self.spans:
                if span.is_root:
                    object.__setattr__(self, "root_service", span.service_name)
                    break

    @property
    def num_spans(self) -> int:
        return len(self.spans)

    @property
    def is_simple(self) -> bool:
        return len(self.spans) == 1

    @cached_property
    def span_map(self) -> dict[str, Span]:
        return {s.span_id: s for s in self.spans}
