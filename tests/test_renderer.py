from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from src.renderer.interactive import render_interactive
from src.renderer.static import render_static


def build_render_test_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_edge("frontend", "cartservice", weight=100, durations=np.random.normal(50, 5, 100).tolist())
    G.add_edge("cartservice", "redis-cart", weight=80, durations=np.random.normal(10, 2, 80).tolist())
    G.add_edge("frontend", "checkoutservice", weight=50, durations=np.random.normal(100, 10, 50).tolist())
    G.add_edge("checkoutservice", "shippingservice", weight=40, durations=np.random.normal(200, 20, 40).tolist())
    return G


class TestRenderInteractive:
    def test_creates_html_file(self):
        G = build_render_test_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.html"
            result = render_interactive(G, output_path=path)
            assert result == str(path)
            assert path.exists()
            content = path.read_text()
            assert "<html>" in content or "vis.js" in content or "Network" in content

    def test_with_anomalies(self):
        G = build_render_test_graph()
        anomalies = {
            "frontend": {"status": "healthy", "score": 0.01, "p95_baseline_ms": 55},
            "cartservice": {"status": "critical", "score": 0.25, "p95_baseline_ms": 80},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_anomaly.html"
            result = render_interactive(G, anomalies, output_path=path)
            assert result == str(path)


DOT_AVAILABLE = shutil.which("dot") is not None

class TestRenderStatic:
    @pytest.mark.skipif(not DOT_AVAILABLE, reason="graphviz 'dot' executable not found on PATH")
    def test_creates_png_file(self):
        G = build_render_test_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test"
            result = render_static(G, output_path=path, fmt="png")
            assert result == str(path.with_suffix(".png"))
            assert Path(result).exists()

    @pytest.mark.skipif(not DOT_AVAILABLE, reason="graphviz 'dot' executable not found on PATH")
    def test_creates_svg_file(self):
        G = build_render_test_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test"
            result = render_static(G, output_path=path, fmt="svg")
            assert result == str(path.with_suffix(".svg"))
            assert Path(result).exists()

    @pytest.mark.skipif(not DOT_AVAILABLE, reason="graphviz 'dot' executable not found on PATH")
    def test_with_anomalies_coloring(self):
        G = build_render_test_graph()
        anomalies = {
            "frontend": {"status": "healthy", "score": 0.01},
            "cartservice": {"status": "degraded", "score": 0.08},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test"
            result = render_static(G, anomalies, output_path=path, fmt="png")
            assert Path(result).exists()
