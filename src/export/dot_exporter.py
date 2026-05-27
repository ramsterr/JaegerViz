from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)


def export_dot(
    graph: nx.DiGraph,
    output_path: str | Path,
) -> str:
    path = Path(output_path)
    lines = ["digraph {"]
    for node in graph.nodes():
        lines.append(f'  "{node}";')
    for u, v, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        avg_ms = data.get("avg_duration_ms", "")
        label = f"calls:{weight}"
        if avg_ms:
            label += f"\\navg:{avg_ms:.1f}ms"
        lines.append(f'  "{u}" -> "{v}" [label="{label}", weight={weight}];')
    lines.append("}")
    path.write_text("\n".join(lines) + "\n")
    logger.info("Exported graph DOT to %s", path)
    return str(path)
