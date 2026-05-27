from __future__ import annotations

import networkx as nx

from src.graph.builder import build_dependency_graph, filter_subgraph
from src.models.span import Span
from src.models.trace import Trace


def make_span(
    trace_id: str = "t1",
    span_id: str = "s1",
    parent_id: str | None = None,
    service_name: str = "svc-a",
    duration_micros: int = 10000,
) -> Span:
    return Span(
        trace_id=trace_id, span_id=span_id, parent_id=parent_id,
        service_name=service_name, operation_name="op",
        start_time_micros=1000000, duration_micros=duration_micros,
    )


class TestBuildDependencyGraph:
    def test_simple_parent_child(self):
        root = make_span(span_id="s1", parent_id=None, service_name="frontend")
        child = make_span(span_id="s2", parent_id="s1", service_name="backend", duration_micros=5000)
        trace = Trace(trace_id="t1", spans=[root, child])
        G = build_dependency_graph([trace])

        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1
        assert G.has_edge("frontend", "backend")
        assert G.edges["frontend", "backend"]["weight"] == 1
        assert G.edges["frontend", "backend"]["durations"] == [5.0]

    def test_multiple_calls_same_edge(self):
        root = make_span(span_id="s1", parent_id=None, service_name="frontend")
        c1 = make_span(span_id="s2", parent_id="s1", service_name="backend", duration_micros=5000)
        c2 = make_span(span_id="s3", parent_id="s1", service_name="backend", duration_micros=7000)
        trace = Trace(trace_id="t1", spans=[root, c1, c2])
        G = build_dependency_graph([trace])

        assert G.edges["frontend", "backend"]["weight"] == 2
        assert len(G.edges["frontend", "backend"]["durations"]) == 2

    def test_missing_parent_skipped(self):
        child = make_span(span_id="s2", parent_id="nonexistent", service_name="backend")
        trace = Trace(trace_id="t1", spans=[child])
        G = build_dependency_graph([trace])

        assert "backend" in G.nodes
        assert G.number_of_edges() == 0

    def test_single_span_trace_adds_node(self):
        span = make_span(service_name="lone-service")
        trace = Trace(trace_id="t1", spans=[span])
        G = build_dependency_graph([trace])

        assert "lone-service" in G.nodes
        assert G.number_of_edges() == 0

    def test_edge_stats_computed(self):
        root = make_span(span_id="s1", service_name="frontend")
        child = make_span(span_id="s2", parent_id="s1", service_name="backend", duration_micros=5000)
        trace = Trace(trace_id="t1", spans=[root, child])
        G = build_dependency_graph([trace])

        data = G.edges["frontend", "backend"]
        assert "avg_duration_ms" in data
        assert "p50_duration_ms" in data
        assert "p95_duration_ms" in data
        assert "p99_duration_ms" in data
        assert "min_duration_ms" in data
        assert "max_duration_ms" in data

    def test_diamond_topology(self):
        t1_root = make_span("t1", "root", None, "frontend")
        t1_a = make_span("t1", "a", "root", "svc-a", 10000)
        t1_b = make_span("t1", "b", "root", "svc-b", 10000)
        t1_db = make_span("t1", "db-a", "a", "database", 5000)
        t1_db2 = make_span("t1", "db-b", "b", "database", 5000)
        trace1 = Trace("t1", [t1_root, t1_a, t1_b, t1_db, t1_db2])

        t2_root = make_span("t2", "root2", None, "frontend")
        t2_a = make_span("t2", "a2", "root2", "svc-a", 10000)
        t2_db = make_span("t2", "db2", "a2", "database", 5000)
        trace2 = Trace("t2", [t2_root, t2_a, t2_db])

        G = build_dependency_graph([trace1, trace2])

        assert G.number_of_nodes() == 4
        assert G.has_edge("frontend", "svc-a")
        assert G.has_edge("frontend", "svc-b")
        assert G.has_edge("svc-a", "database")
        assert G.has_edge("svc-b", "database")
        assert G.edges["svc-a", "database"]["weight"] == 2
        assert G.edges["svc-b", "database"]["weight"] == 1


class TestFilterSubgraph:
    def test_filter_by_service(self):
        G = nx.DiGraph()
        G.add_edge("frontend", "cartservice", weight=10)
        G.add_edge("cartservice", "redis", weight=5)
        G.add_edge("frontend", "shippingservice", weight=3)
        G.add_edge("shippingservice", "redis", weight=2)

        sub = filter_subgraph(G, "cartservice", hops=1)

        assert "cartservice" in sub.nodes
        assert "frontend" in sub.nodes
        assert "redis" in sub.nodes
        assert "shippingservice" not in sub.nodes

    def test_filter_unknown_service_raises(self):
        G = nx.DiGraph()
        G.add_node("frontend")

        import pytest
        with pytest.raises(ValueError, match="Service 'unknown' not found"):
            filter_subgraph(G, "unknown")
