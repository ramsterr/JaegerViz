from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    service_name: str
    operation_name: str
    start_time_micros: int
    duration_micros: int
    is_error: bool = False
    tags: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.parent_id in ("0", ""):
            object.__setattr__(self, "parent_id", None)

    @property
    def duration_ms(self) -> float:
        return self.duration_micros / 1000.0

    @property
    def duration_s(self) -> float:
        return self.duration_micros / 1_000_000.0

    @property
    def is_root(self) -> bool:
        return self.parent_id is None
