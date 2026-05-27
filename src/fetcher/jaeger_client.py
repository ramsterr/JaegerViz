from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.models.trace import Trace
from src.models.span import Span
from src.utils.timing import micros_to_seconds

logger = logging.getLogger(__name__)


class JaegerClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        rate_limit_ms: int = 100,
        max_pages: int = 50,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.rate_limit_ms = rate_limit_ms
        self.max_pages = max_pages
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"

    def fetch(
        self,
        service: Optional[str] = None,
        lookback: str = "1h",
        limit: int = 100,
        operation: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> list[Trace]:
        params = {"limit": limit, "lookback": lookback}
        if service:
            params["service"] = service
        if operation:
            params["operation"] = operation
        if tags:
            tag_parts = []
            for k, v in tags.items():
                tag_parts.append(f"{k}:{v}")
            params["tags"] = ",".join(tag_parts)

        return self._paginate("/api/traces", params)

    def fetch_range(
        self,
        service: Optional[str] = None,
        start_seconds: Optional[float] = None,
        end_seconds: Optional[float] = None,
        limit: int = 100,
        operation: Optional[str] = None,
    ) -> list[Trace]:
        params: dict = {"limit": limit}
        if service:
            params["service"] = service
        if operation:
            params["operation"] = operation
        if start_seconds is not None:
            params["start"] = int(start_seconds * 1_000_000)
        if end_seconds is not None:
            params["end"] = int(end_seconds * 1_000_000)

        return self._paginate("/api/traces", params)

    def _paginate(self, path: str, base_params: dict) -> list[Trace]:
        all_traces: list[Trace] = []
        offset = 0
        page = 0

        while page < self.max_pages:
            params = {**base_params, "offset": offset}
            url = f"{self.base_url}{path}"

            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                logger.error("Jaeger API request failed: %s", e)
                break

            if resp.status_code != 200:
                logger.error(
                    "Jaeger API returned %d: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                break

            data = resp.json()
            traces_raw = data.get("data", []) or data.get("traces", [])
            if isinstance(traces_raw, list) and traces_raw and isinstance(traces_raw[0], dict):
                for tr in traces_raw:
                    trace = self._parse_trace(tr)
                    if trace.num_spans > 0:
                        all_traces.append(trace)
            elif isinstance(traces_raw, list) and traces_raw and isinstance(traces_raw[0], list):
                traces_raw = traces_raw[0]
                for tr in traces_raw:
                    trace = self._parse_trace(tr)
                    if trace.num_spans > 0:
                        all_traces.append(trace)

            total = data.get("total", 0)
            offset += len(traces_raw) if isinstance(traces_raw, list) else 0
            page += 1

            if len(traces_raw) < 1 or offset >= total or total == 0:
                break

            time.sleep(self.rate_limit_ms / 1000.0)

        logger.info("Fetched %d traces across %d pages", len(all_traces), page)
        return all_traces

    def _parse_trace(self, trace_data: dict) -> Trace:
        trace_id = trace_data.get("traceID", "")
        processes = trace_data.get("processes", {})
        spans_raw = trace_data.get("spans", [])

        spans: list[Span] = []
        for span_data in spans_raw:
            process_id = span_data.get("processID", "")
            process = processes.get(process_id, {})
            service_name = process.get("serviceName", "unknown")

            parent_id = span_data.get("parentSpanID", "")
            if parent_id in ("0", ""):
                parent_id = None

            is_error = False
            tags_list = span_data.get("tags", [])
            tags_dict: dict[str, str] = {}
            for tag in tags_list:
                key = tag.get("key", "")
                value = tag.get("value", "")
                tags_dict[key] = str(value)
                if key == "error" and str(value).lower() in ("true", "1"):
                    is_error = True

            span = Span(
                trace_id=trace_id,
                span_id=span_data.get("spanID", ""),
                parent_id=parent_id,
                service_name=service_name,
                operation_name=span_data.get("operationName", ""),
                start_time_micros=int(span_data.get("startTime", 0)),
                duration_micros=int(span_data.get("duration", 0)),
                is_error=is_error,
                tags=tags_dict,
            )
            spans.append(span)

        return Trace(trace_id=trace_id, spans=spans)

    def close(self):
        self._session.close()
