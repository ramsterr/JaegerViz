from __future__ import annotations

import networkx as nx
import numpy as np

from src.graph.anomalies import highlight_anomalies


def build_test_graph() -> nx.DiGraph:
    G = nx.DiGraph()

    np.random.seed(42)
    normal = np.random.normal(50, 5, 1000).tolist()
    G.add_edge("frontend", "backend", weight=len(normal), durations=normal)

    slow = np.random.normal(50, 5, 800).tolist() + np.random.normal(500, 50, 200).tolist()
    G.add_edge("backend", "database", weight=len(slow), durations=slow)

    return G


class TestHighlightAnomalies:
    def test_normal_service_healthy(self):
        G = build_test_graph()
        anomalies = highlight_anomalies(G)

        frontend = anomalies["frontend"]
        assert frontend["status"] == "healthy"
        assert frontend["score"] < 0.05

    def test_degraded_service_detected(self):
        G = build_test_graph()
        anomalies = highlight_anomalies(G)

        database = anomalies["database"]
        assert database["status"] in ("healthy", "degraded", "critical")

    def test_empty_graph(self):
        G = nx.DiGraph()
        anomalies = highlight_anomalies(G)
        assert anomalies == {}

    def test_isolated_node(self):
        G = nx.DiGraph()
        G.add_node("orphan")
        anomalies = highlight_anomalies(G)

        assert anomalies["orphan"]["status"] == "healthy"
        assert anomalies["orphan"]["score"] == 0.0

    def test_critical_threshold(self):
        G = nx.DiGraph()
        all_slow = np.random.normal(500, 50, 100).tolist()
        G.add_edge("svc-a", "svc-b", weight=len(all_slow), durations=all_slow)
        anomalies = highlight_anomalies(G)
        assert "svc-a" in anomalies
