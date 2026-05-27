from __future__ import annotations

import logging
from collections import defaultdict

import networkx as nx
import numpy as np

from src.models.trace import Trace

logger = logging.getLogger(__name__)


def build_dependency_graph(traces: list[Trace]) -> nx.DiGraph:
    G = nx.DiGraph()
    edge_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

    for trace in traces:
        if trace.is_simple:
            span = trace.spans[0]
            G.add_node(span.service_name)
            continue

        span_map = trace.span_map
        for span in trace.spans:
            if span.parent_id is None:
                G.add_node(span.service_name)
                continue

            parent = span_map.get(span.parent_id)
            if parent is None:
                continue

            edge = (parent.service_name, span.service_name)
            edge_durations[edge].append(span.duration_ms)

    for (u, v), durations in edge_durations.items():
        arr = np.array(durations)
        G.add_edge(
            u,
            v,
            weight=len(durations),
            durations=durations,
            avg_duration_ms=float(np.mean(arr)),
            p50_duration_ms=float(np.percentile(arr, 50)),
            p95_duration_ms=float(np.percentile(arr, 95)),
            p99_duration_ms=float(np.percentile(arr, 99)),
            min_duration_ms=float(np.min(arr)),
            max_duration_ms=float(np.max(arr)),
        )

    logger.info(
        "Built graph: %d nodes, %d edges from %d traces",
        G.number_of_nodes(),
        G.number_of_edges(),
        len(traces),
    )
    return G


def filter_subgraph(
    graph: nx.DiGraph,
    service: str,
    hops: int = 1,
) -> nx.DiGraph:
    if service not in graph:
        raise ValueError(f"Service '{service}' not found in graph. Available: {sorted(graph.nodes())}")

    nodes = {service}
    frontier = {service}
    for _ in range(hops):
        next_frontier: set[str] = set()
        for node in frontier:
            next_frontier.update(graph.predecessors(node))
            next_frontier.update(graph.successors(node))
        frontier = next_frontier - nodes
        nodes.update(frontier)

    return graph.subgraph(nodes).copy()
