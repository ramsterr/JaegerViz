from __future__ import annotations

import pytest

from src.models.span import Span
from src.models.trace import Trace
from .conftest import make_span, make_trace


class TestSpan:
    def test_parent_id_normalisation_empty_string(self):
        span = Span(
            trace_id="t1", span_id="s1", parent_id="",
            service_name="svc", operation_name="op",
            start_time_micros=0, duration_micros=1000,
        )
        assert span.parent_id is None
        assert span.is_root is True

    def test_parent_id_normalisation_zero(self):
        span = Span(
            trace_id="t1", span_id="s1", parent_id="0",
            service_name="svc", operation_name="op",
            start_time_micros=0, duration_micros=1000,
        )
        assert span.parent_id is None
        assert span.is_root is True

    def test_duration_ms_conversion(self):
        span = make_span(duration_micros=5000)
        assert span.duration_ms == 5.0

    def test_duration_s_conversion(self):
        span = make_span(duration_micros=2_000_000)
        assert span.duration_s == 2.0

    def test_is_error_default(self):
        span = make_span()
        assert span.is_error is False

    def test_is_error_true(self):
        span = make_span(is_error=True)
        assert span.is_error is True

    def test_tags_default_empty(self):
        span = make_span()
        assert span.tags == {}


class TestTrace:
    def test_root_service_detected(self):
        root = make_span(parent_id=None, service_name="frontend")
        child = make_span(span_id="s2", parent_id="s1", service_name="backend")
        trace = Trace(trace_id="t1", spans=[root, child])
        assert trace.root_service == "frontend"

    def test_is_simple_single_span(self):
        span = make_span()
        trace = Trace(trace_id="t1", spans=[span])
        assert trace.is_simple is True
        assert trace.num_spans == 1

    def test_is_simple_multiple_spans(self):
        s1 = make_span(span_id="s1")
        s2 = make_span(span_id="s2", parent_id="s1")
        trace = Trace(trace_id="t1", spans=[s1, s2])
        assert trace.is_simple is False

    def test_span_map_lookup(self):
        s1 = make_span(span_id="s1", service_name="frontend")
        s2 = make_span(span_id="s2", parent_id="s1", service_name="backend")
        trace = Trace(trace_id="t1", spans=[s1, s2])
        assert trace.span_map["s1"].service_name == "frontend"
        assert trace.span_map["s2"].service_name == "backend"

    def test_root_service_none_when_no_root(self):
        s1 = make_span(span_id="s1", parent_id="s2")
        s2 = make_span(span_id="s2", parent_id="s1")
        trace = Trace(trace_id="t1", spans=[s1, s2])
        assert trace.root_service is None
