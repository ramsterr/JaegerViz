from __future__ import annotations

from unittest import mock

from src.fetcher.jaeger_client import JaegerClient
from src.models.span import Span
from .conftest import JAEGER_TRACE_RESPONSE


class TestJaegerClient:
    def test_parse_trace_structure(self):
        client = JaegerClient("http://localhost:16686")
        trace_data = JAEGER_TRACE_RESPONSE["data"][0]
        trace = client._parse_trace(trace_data)

        assert trace.trace_id == "trace-abc123"
        assert trace.num_spans == 3
        assert trace.root_service == "frontend"

    def test_parse_trace_service_names(self):
        client = JaegerClient("http://localhost:16686")
        trace_data = JAEGER_TRACE_RESPONSE["data"][0]
        trace = client._parse_trace(trace_data)

        names = {s.service_name for s in trace.spans}
        assert names == {"frontend", "redis", "database"}

    def test_parse_trace_root_span(self):
        client = JaegerClient("http://localhost:16686")
        trace_data = JAEGER_TRACE_RESPONSE["data"][0]
        trace = client._parse_trace(trace_data)

        root = next(s for s in trace.spans if s.is_root)
        assert root.service_name == "frontend"
        assert root.operation_name == "GET /cart"

    def test_parse_trace_child_span(self):
        client = JaegerClient("http://localhost:16686")
        trace_data = JAEGER_TRACE_RESPONSE["data"][0]
        trace = client._parse_trace(trace_data)

        child = next(s for s in trace.spans if s.span_id == "child-1")
        assert child.service_name == "redis"
        assert child.parent_id == "root-1"
        assert child.is_error is True

    def test_parse_trace_empty_spans(self):
        client = JaegerClient("http://localhost:16686")
        trace_data = {"traceID": "empty", "spans": [], "processes": {}}
        trace = client._parse_trace(trace_data)
        assert trace.num_spans == 0

    def test_fetch_pagination(self):
        client = JaegerClient("http://localhost:16686")
        data = [
            {
                "traceID": "t1",
                "spans": [{
                    "spanID": "s1", "parentSpanID": "",
                    "operationName": "op", "startTime": 1, "duration": 1000,
                    "processID": "p1", "tags": [],
                }],
                "processes": {"p1": {"serviceName": "svc"}},
            },
            {
                "traceID": "t2",
                "spans": [{
                    "spanID": "s2", "parentSpanID": "",
                    "operationName": "op", "startTime": 2, "duration": 2000,
                    "processID": "p1", "tags": [],
                }],
                "processes": {"p1": {"serviceName": "svc"}},
            },
        ]

        with mock.patch.object(client._session, "get") as mock_get:
            mock_resp = mock.MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": data, "total": 2, "limit": 100}
            mock_get.return_value = mock_resp

            traces = client._paginate("/api/traces", {"limit": 100})
            assert len(traces) == 2

    def test_close_cleans_up(self):
        client = JaegerClient("http://localhost:16686")
        client.close()
