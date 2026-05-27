from __future__ import annotations

import json
from typing import Optional

import pytest

from src.models.span import Span
from src.models.trace import Trace


def make_span(
    trace_id: str = "trace-1",
    span_id: str = "span-1",
    parent_id: str | None = None,
    service_name: str = "service-a",
    operation_name: str = "GET /api",
    duration_micros: int = 5000,
    is_error: bool = False,
) -> Span:
    return Span(
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent_id,
        service_name=service_name,
        operation_name=operation_name,
        start_time_micros=1000000,
        duration_micros=duration_micros,
        is_error=is_error,
    )


def make_trace(
    trace_id: str = "trace-1",
    spans: list[Span] | None = None,
) -> Trace:
    if spans is None:
        spans = []
    return Trace(trace_id=trace_id, spans=spans)


JAEGER_TRACE_RESPONSE = {
    "data": [
        {
            "traceID": "trace-abc123",
            "spans": [
                {
                    "spanID": "root-1",
                    "parentSpanID": "",
                    "operationName": "GET /cart",
                    "startTime": 1600000000000000,
                    "duration": 500000,
                    "processID": "p1",
                    "tags": [],
                },
                {
                    "spanID": "child-1",
                    "parentSpanID": "root-1",
                    "operationName": "redis:GET",
                    "startTime": 1600000000010000,
                    "duration": 2000,
                    "processID": "p2",
                    "tags": [{"key": "error", "value": True}],
                },
                {
                    "spanID": "child-2",
                    "parentSpanID": "root-1",
                    "operationName": "db:query",
                    "startTime": 1600000000020000,
                    "duration": 15000,
                    "processID": "p3",
                    "tags": [],
                },
            ],
            "processes": {
                "p1": {"serviceName": "frontend", "tags": []},
                "p2": {"serviceName": "redis", "tags": []},
                "p3": {"serviceName": "database", "tags": []},
            },
        }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0,
}
