from __future__ import annotations

import logging
from collections import defaultdict

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


def highlight_anomalies(graph: nx.DiGraph) -> dict[str, dict]:
    service_durations: dict[str, list[float]] = defaultdict(list)

    for u, v, data in graph.edges(data=True):
        durations = data.get("durations", [])
        service_durations[u].extend(durations)
        service_durations[v].extend(durations)

    anomalies: dict[str, dict] = {}
    for service in graph.nodes():
        durations = service_durations.get(service, [])
        if not durations:
            anomalies[service] = {"score": 0.0, "status": "healthy"}
            continue

        arr = np.array(durations)
        p95 = float(np.percentile(arr, 95))
        threshold = p95 * 2.0

        if p95 == 0:
            anomalies[service] = {"score": 0.0, "status": "healthy"}
            continue

        anomalous_count = int(np.sum(arr > threshold))
        score = anomalous_count / len(arr)

        if score < 0.05:
            status = "healthy"
        elif score < 0.15:
            status = "degraded"
        else:
            status = "critical"

        anomalies[service] = {
            "score": round(score, 4),
            "status": status,
            "total_spans": len(arr),
            "anomalous_spans": anomalous_count,
            "p95_baseline_ms": round(p95, 2),
        }

    logger.info(
        "Anomaly analysis: %d services — healthy=%d, degraded=%d, critical=%d",
        len(anomalies),
        sum(1 for a in anomalies.values() if a["status"] == "healthy"),
        sum(1 for a in anomalies.values() if a["status"] == "degraded"),
        sum(1 for a in anomalies.values() if a["status"] == "critical"),
    )
    return anomalies
