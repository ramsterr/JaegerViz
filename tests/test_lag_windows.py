from __future__ import annotations

import json
from pathlib import Path
import tempfile

import networkx as nx
import numpy as np

from src.graph.lag_windows import compute_lag_windows, export_lag_windows


def build_lag_test_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    sync_durations = np.random.normal(200, 20, 500).tolist()
    G.add_edge("frontend", "cartservice", weight=len(sync_durations), durations=sync_durations)

    async_durations = np.random.normal(120_000, 10_000, 200).tolist()
    G.add_edge("cartservice", "emailservice", weight=len(async_durations), durations=async_durations)

    return G


class TestComputeLagWindows:
    def test_sync_edge_clamped_to_minimum(self):
        G = build_lag_test_graph()
        windows = compute_lag_windows(G)

        lag = windows[("frontend", "cartservice")]
        assert lag == 1.0

    def test_async_edge_returns_larger_window(self):
        G = build_lag_test_graph()
        windows = compute_lag_windows(G)

        lag = windows[("cartservice", "emailservice")]
        assert lag > 1.0

    def test_empty_durations_fallback(self):
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=0, durations=[])
        windows = compute_lag_windows(G)

        assert windows[("a", "b")] == 10.0

    def test_clamp_to_max(self):
        G = nx.DiGraph()
        G.add_edge("slow", "very-slow", weight=1, durations=[360_000.0])
        windows = compute_lag_windows(G)

        assert windows[("slow", "very-slow")] == 30.0


class TestExportLagWindows:
    def test_export_creates_valid_json(self):
        G = build_lag_test_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lag_output.json"
            result = export_lag_windows(G, path)

            assert result == str(path)
            data = json.loads(path.read_text())
            assert "edges" in data
            assert len(data["edges"]) == 2
            assert data["edges"][0]["source"] in ("frontend", "cartservice")
