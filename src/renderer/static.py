from __future__ import annotations

import logging
from pathlib import Path

import graphviz
import networkx as nx

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "healthy": "#4CAF50",
    "degraded": "#FFC107",
    "critical": "#F44336",
}
DEFAULT_COLOR = "#9E9E9E"


def render_static(
    graph: nx.DiGraph,
    anomalies: dict[str, dict] | None = None,
    output_path: str | Path = "topology",
    fmt: str = "png",
    engine: str = "dot",
) -> str:
    if anomalies is None:
        anomalies = {}

    dot = graphviz.Digraph(format=fmt, engine=engine)
    dot.attr(rankdir="LR", bgcolor="white", fontname="Helvetica")

    max_weight = max(
        (data.get("weight", 1) for _, _, data in graph.edges(data=True)),
        default=1,
    )

    for node in graph.nodes():
        status = anomalies.get(node, {}).get("status", "healthy")
        color = STATUS_COLORS.get(status, DEFAULT_COLOR)
        score = anomalies.get(node, {}).get("score", 0)

        label_parts = [node]
        if score > 0:
            label_parts.append(f"({status})")

        dot.node(
            node,
            label="\n".join(label_parts),
            style="filled",
            fillcolor=color,
            fontcolor="white",
            shape="box",
            fontname="Helvetica",
        )

    for u, v, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        penwidth = str(max(1, (weight / max_weight) * 5) * 0.5)
        avg_ms = data.get("avg_duration_ms")

        label = f"calls:{weight}"
        if avg_ms is not None:
            label += f"\navg:{avg_ms:.1f}ms"

        dot.edge(
            u,
            v,
            label=label,
            penwidth=penwidth,
            fontsize="10",
            fontname="Helvetica",
        )

    path = Path(output_path)
    stem = str(path.with_suffix(""))
    dot.render(stem, cleanup=True)
    actual_path = f"{stem}.{fmt}"
    logger.info("Static graph saved to %s", actual_path)
    return actual_path
