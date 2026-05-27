from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

MIN_LAG_MINUTES = 1.0
MAX_LAG_MINUTES = 30.0
SAFETY_MULTIPLIER = 10.0
FALLBACK_LAG_MINUTES = 10.0


def compute_lag_windows(graph: nx.DiGraph) -> dict[tuple[str, str], float]:
    windows: dict[tuple[str, str], float] = {}
    for u, v, data in graph.edges(data=True):
        durations = data.get("durations", [])
        if not durations:
            windows[(u, v)] = FALLBACK_LAG_MINUTES
            continue

        p99 = float(np.percentile(durations, 99))
        lag_minutes = max(
            MIN_LAG_MINUTES,
            min(MAX_LAG_MINUTES, (p99 / 1000.0 / 60.0) * SAFETY_MULTIPLIER),
        )
        windows[(u, v)] = round(lag_minutes, 2)

    return windows


def export_lag_windows(
    graph: nx.DiGraph,
    output_path: str | Path,
) -> str:
    windows = compute_lag_windows(graph)

    edges_data = []
    for (u, v), lag_minutes in windows.items():
        data = graph.edges[u, v]
        p99_ms = data.get("p99_duration_ms", 0)
        edges_data.append({
            "source": u,
            "target": v,
            "lag_minutes": lag_minutes,
            "p99_duration_ms": round(p99_ms, 2),
            "call_count": data.get("weight", 0),
        })

    output = {
        "description": "Per-edge maximum correlation lag windows for causal analysis",
        "min_lag_minutes": MIN_LAG_MINUTES,
        "max_lag_minutes": MAX_LAG_MINUTES,
        "safety_multiplier": SAFETY_MULTIPLIER,
        "edges": edges_data,
    }

    path = Path(output_path)
    path.write_text(json.dumps(output, indent=2))
    logger.info("Exported lag windows to %s (%d edges)", path, len(edges_data))
    return str(path)
