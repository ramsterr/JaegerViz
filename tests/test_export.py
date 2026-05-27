from __future__ import annotations

import json
import tempfile
from pathlib import Path

import networkx as nx

from src.export.json_exporter import export_json
from src.export.dot_exporter import export_dot


class TestExportJson:
    def test_exports_valid_node_link_format(self):
        G = nx.DiGraph()
        G.add_edge("frontend", "backend", weight=10, durations=[5.0, 7.0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            result = export_json(G, path)

            assert result == str(path)
            data = json.loads(path.read_text())
            assert "nodes" in data
            assert "links" in data
            assert len(data["nodes"]) == 2
            assert len(data["links"]) == 1

    def test_durations_removed_from_json(self):
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=5, durations=[1.0, 2.0, 3.0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            export_json(G, path)
            data = json.loads(path.read_text())
            link = data["links"][0]
            assert "durations" not in link
            assert link["weight"] == 5


class TestExportDot:
    def test_exports_dot_format(self):
        G = nx.DiGraph()
        G.add_edge("frontend", "backend", weight=10)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.dot"
            result = export_dot(G, path)

            assert result == str(path)
            content = path.read_text()
            assert "diGraph" in content or "digraph" in content
            assert "frontend" in content
            assert "backend" in content
