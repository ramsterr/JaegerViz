from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)


def export_json(
    graph: nx.DiGraph,
    output_path: str | Path,
) -> str:
    data = nx.node_link_data(graph)

    for link in data.get("links", []):
        if "durations" in link:
            del link["durations"]

    path = Path(output_path)
    path.write_text(json.dumps(data, indent=2))
    logger.info("Exported graph JSON to %s", path)
    return str(path)
