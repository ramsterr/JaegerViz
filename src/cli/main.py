from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from src.fetcher.jaeger_client import JaegerClient
from src.graph.builder import build_dependency_graph, filter_subgraph
from src.graph.anomalies import highlight_anomalies as compute_anomalies
from src.graph.lag_windows import export_lag_windows
from src.renderer.interactive import render_interactive
from src.renderer.static import render_static
from src.export.json_exporter import export_json
from src.export.dot_exporter import export_dot
from src.models.span import Span
from src.models.trace import Trace

logger = logging.getLogger(__name__)


def _load_traces_from_file(filepath: str) -> list[Trace]:
    path = Path(filepath)
    if not path.exists():
        raise click.BadParameter(f"File not found: {filepath}")

    data = json.loads(path.read_text())
    traces_raw = data.get("data", []) or data.get("traces", [])
    if isinstance(traces_raw, list) and traces_raw and isinstance(traces_raw[0], list):
        traces_raw = traces_raw[0]

    client = JaegerClient(base_url="http://localhost:16686")
    traces: list[Trace] = []
    for tr in traces_raw:
        if isinstance(tr, dict):
            trace = client._parse_trace(tr)
            if trace.num_spans > 0:
                traces.append(trace)
    return traces


def _fetch_traces(
    from_file: Optional[str],
    jaeger_url: str,
    lookback: str,
    service: Optional[str],
    limit: int,
    operation: Optional[str] = None,
) -> list[Trace]:
    if from_file:
        click.echo(f"Loading traces from {from_file} ...")
        return _load_traces_from_file(from_file)

    click.echo(f"Connecting to Jaeger at {jaeger_url} ...")
    client = JaegerClient(base_url=jaeger_url)
    try:
        traces = client.fetch(
            service=service,
            lookback=lookback,
            limit=limit,
            operation=operation,
        )
    finally:
        client.close()
    return traces


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Service Topology Manager — trace-based microservice dependency graph visualizer."""
    pass


@cli.command()
@click.option("--from-file", default=None, help="Load traces from a local JSON file instead of Jaeger.")
@click.option("--jaeger-url", default="http://localhost:16686", help="Jaeger query service URL.")
@click.option("--lookback", default="1h", help="Time window (e.g. 1h, 30m, 15m).")
@click.option("--service", default=None, help="Filter to a specific service and its neighbors.")
@click.option("--operation", default=None, help="Filter by operation name.")
@click.option("--hops", default=1, help="Neighbor depth when filtering by service.")
@click.option("--format", "output_format", default="html", type=click.Choice(["html", "png", "svg"]), help="Output format.")
@click.option("--output", default=None, help="Output file path.")
@click.option("--highlight-anomalies/--no-highlight-anomalies", default=False, help="Enable anomaly highlighting.")
@click.option("--limit", default=100, help="Max traces per page from Jaeger.")
def render(
    from_file: str | None,
    jaeger_url: str,
    lookback: str,
    service: str | None,
    operation: str | None,
    hops: int,
    output_format: str,
    output: str | None,
    highlight_anomalies: bool,
    limit: int,
):
    """Fetch traces from Jaeger (or local file) and render the dependency graph."""
    traces = _fetch_traces(from_file, jaeger_url, lookback, service, limit, operation)

    if not traces:
        click.echo("No traces found.", err=True)
        sys.exit(1)

    click.echo(f"Loaded {len(traces)} traces. Building dependency graph ...")
    graph = build_dependency_graph(traces)

    if service and hops:
        try:
            graph = filter_subgraph(graph, service, hops)
        except ValueError as e:
            click.echo(str(e), err=True)
            sys.exit(1)

    anomalies = None
    if highlight_anomalies:
        click.echo("Computing anomaly scores ...")
        anomalies = compute_anomalies(graph)
        for svc, info in sorted(anomalies.items()):
            click.echo(f"  {svc}: {info['status']} (score={info['score']})")

    if output_format == "html":
        out = output or "topology.html"
        path = render_interactive(graph, anomalies, output_path=out)
    else:
        out = output or f"topology.{output_format}"
        path = render_static(graph, anomalies, output_path=out, fmt=output_format)

    click.echo(f"Graph saved to {path}")
    click.echo(f"Nodes: {graph.number_of_nodes()}, Edges: {graph.number_of_edges()}")


@cli.command()
@click.option("--from-file", default=None, help="Load traces from a local JSON file instead of Jaeger.")
@click.option("--jaeger-url", default="http://localhost:16686", help="Jaeger query service URL.")
@click.option("--lookback", default="1h", help="Time window (e.g. 1h, 30m, 15m).")
@click.option("--service", default=None, help="Filter by service name.")
@click.option("--format", "output_format", default="json", type=click.Choice(["json", "dot"]), help="Export format.")
@click.option("--output", default=None, help="Output file path.")
@click.option("--hops", default=1, help="Neighbor depth when filtering by service.")
@click.option("--limit", default=100, help="Max traces per page from Jaeger.")
def export(
    from_file: str | None,
    jaeger_url: str,
    lookback: str,
    service: str | None,
    output_format: str,
    output: str | None,
    hops: int,
    limit: int,
):
    """Export the dependency graph as JSON or DOT."""
    traces = _fetch_traces(from_file, jaeger_url, lookback, service, limit)

    if not traces:
        click.echo("No traces found.", err=True)
        sys.exit(1)

    click.echo(f"Loaded {len(traces)} traces. Building dependency graph ...")
    graph = build_dependency_graph(traces)

    if service and hops:
        try:
            graph = filter_subgraph(graph, service, hops)
        except ValueError as e:
            click.echo(str(e), err=True)
            sys.exit(1)

    if output_format == "json":
        out = output or "graph.json"
        path = export_json(graph, out)
    else:
        out = output or "graph.dot"
        path = export_dot(graph, out)

    click.echo(f"Graph exported to {path}")
    click.echo(f"Nodes: {graph.number_of_nodes()}, Edges: {graph.number_of_edges()}")


@cli.command()
@click.option("--from-file", default=None, help="Load traces from a local JSON file instead of Jaeger.")
@click.option("--jaeger-url", default="http://localhost:16686", help="Jaeger query service URL.")
@click.option("--lookback", default="1h", help="Time window (e.g. 1h, 30m, 15m).")
@click.option("--service", default=None, help="Filter by service name.")
@click.option("--output", default="lag_windows.json", help="Output file path.")
@click.option("--limit", default=100, help="Max traces per page from Jaeger.")
def lag_windows(
    from_file: str | None,
    jaeger_url: str,
    lookback: str,
    service: str | None,
    output: str,
    limit: int,
):
    """Export per-edge correlation lag windows for causal analysis (Project 5)."""
    traces = _fetch_traces(from_file, jaeger_url, lookback, service, limit)

    if not traces:
        click.echo("No traces found.", err=True)
        sys.exit(1)

    click.echo(f"Loaded {len(traces)} traces. Building dependency graph ...")
    graph = build_dependency_graph(traces)

    path = export_lag_windows(graph, output)

    windows = {}
    for u, v, data in graph.edges(data=True):
        durs = data.get("durations", [])
        if durs:
            import numpy as np
            p99 = float(np.percentile(durs, 99))
            lag = max(1.0, min(30.0, (p99 / 1000.0 / 60.0) * 10.0))
            windows[(u, v)] = round(lag, 2)

    click.echo(f"Lag windows exported to {path}")
    for (u, v), lag in sorted(windows.items()):
        click.echo(f"  {u} → {v}: {lag} min")
