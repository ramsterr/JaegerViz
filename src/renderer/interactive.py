from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "healthy": "#FF8C00",
    "degraded": "#FF8C00",
    "critical": "#FF8C00",
}
STATUS_BORDERS = {
    "healthy": "#CC7000",
    "degraded": "#CC7000",
    "critical": "#CC7000",
}


def _build_graph_data(graph: nx.DiGraph, anomalies: dict[str, dict]) -> dict:
    nodes = []
    edges = []

    max_degree = max(dict(graph.degree()).values(), default=1)
    max_weight = max(
        (data.get("weight", 1) for _, _, data in graph.edges(data=True)),
        default=1,
    )

    for node in graph.nodes():
        info = anomalies.get(node, {})
        status = info.get("status", "healthy")
        degree = graph.degree(node)
        predecessors = list(graph.predecessors(node))
        successors = list(graph.successors(node))

        in_durations: list[float] = []
        for pred in predecessors:
            d = graph.edges.get((pred, node), {}).get("durations", [])
            if d:
                in_durations.extend(d)
        p95_in = round(float(np.percentile(in_durations, 95)), 1) if in_durations else None

        out_durations: list[float] = []
        for succ in successors:
            d = graph.edges.get((node, succ), {}).get("durations", [])
            if d:
                out_durations.extend(d)
        p95_out = round(float(np.percentile(out_durations, 95)), 1) if out_durations else None

        size = max(20, int((degree / max_degree) * 50)) if max_degree > 0 else 20

        nodes.append({
            "id": node,
            "label": node,
            "size": size,
            "status": status,
            "score": info.get("score", 0),
            "p95_baseline_ms": info.get("p95_baseline_ms"),
            "total_spans": info.get("total_spans", 0),
            "anomalous_spans": info.get("anomalous_spans", 0),
            "degree": degree,
            "in_degree": len(predecessors),
            "out_degree": len(successors),
            "predecessors": predecessors,
            "successors": successors,
            "p95_in_ms": p95_in,
            "p95_out_ms": p95_out,
        })

    for u, v, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        dur_arr = data.get("durations", [])
        p99 = float(np.percentile(dur_arr, 99)) if dur_arr else 0
        p50 = float(np.percentile(dur_arr, 50)) if dur_arr else 0
        avg = float(np.mean(dur_arr)) if dur_arr else 0
        p99_rounded = round(p99, 1)
        width = max(1, (weight / max_weight) * 6) if max_weight > 0 else 1
        op = 0.3 + (weight / max_weight) * 0.4 if max_weight > 0 else 0.5

        lag_minutes = None
        if dur_arr:
            p99_dur = float(np.percentile(dur_arr, 99))
            lag_minutes = round(max(1.0, min(30.0, (p99_dur / 1000 / 60) * 10)), 1)

        edges.append({
            "from": u,
            "to": v,
            "weight": weight,
            "width": round(width, 1),
            "opacity": round(op, 2),
            "avg_ms": round(avg, 1),
            "p50_ms": round(p50, 1),
            "p99_ms": p99_rounded,
            "lag_minutes": lag_minutes,
            "min_ms": round(float(np.min(dur_arr)), 1) if dur_arr else 0,
            "max_ms": round(float(np.max(dur_arr)), 1) if dur_arr else 0,
        })

    return {"nodes": nodes, "edges": edges}


def render_interactive(
    graph: nx.DiGraph,
    anomalies: dict[str, dict] | None = None,
    output_path: str | Path = "topology.html",
    height: str = "750px",
    width: str = "100%",
) -> str:
    if anomalies is None:
        anomalies = {}

    graph_data = _build_graph_data(graph, anomalies)

    html = _build_html(graph_data, graph.number_of_nodes(), graph.number_of_edges())

    path = Path(output_path)
    path.write_text(html)
    logger.info("Interactive graph saved to %s", path)
    return str(path)


def _build_html(graph_data: dict, node_count: int, edge_count: int) -> str:
    nodes_json = json.dumps(graph_data["nodes"])
    edges_json = json.dumps(graph_data["edges"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Service Topology Manager</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: #0d0d0d;
    color: #FFD700;
    overflow: hidden;
    height: 100vh;
    display: flex;
}}

#sidebar {{
    width: 0;
    background: #1a1a1a;
    border-left: 2px solid #FF8C00;
    transition: width 0.3s ease;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}

#sidebar.open {{
    width: 360px;
    min-width: 360px;
}}

#sidebar-header {{
    padding: 16px 20px;
    background: #141414;
    border-bottom: 1px solid #333;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

#sidebar-header h2 {{
    font-size: 16px;
    color: #FF8C00;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

#close-btn {{
    background: none;
    border: 1px solid #555;
    color: #FFD700;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.2s;
}}

#close-btn:hover {{
    background: #FF8C00;
    color: #000;
    border-color: #FF8C00;
}}

#sidebar-body {{
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}}

.section {{
    margin-bottom: 20px;
}}

.section-title {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #888;
    margin-bottom: 10px;
    border-bottom: 1px solid #2a2a2a;
    padding-bottom: 6px;
}}

.stat-row {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 13px;
    border-bottom: 1px solid #1f1f1f;
}}

.stat-row .label {{ color: #999; }}
.stat-row .value {{ color: #FFD700; font-weight: 600; text-align: right; }}

.status-badge {{
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

.status-badge.healthy {{ background: #FF8C00; color: #000; }}
.status-badge.degraded {{ background: #FF8C00; color: #000; border: 1px solid #FFa040; }}
.status-badge.critical {{ background: #FF4500; color: #000; }}

.edge-list {{
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}}

.edge-list li {{
    background: #222;
    border: 1px solid #333;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
    color: #ccc;
}}

.edge-list li:hover {{
    background: #FF8C00;
    color: #000;
    border-color: #FF8C00;
}}

#main-area {{
    flex: 1;
    display: flex;
    flex-direction: column;
}}

#topbar {{
    height: 48px;
    background: #141414;
    border-bottom: 1px solid #2a2a2a;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    min-height: 48px;
}}

#topbar .brand {{
    font-size: 15px;
    font-weight: 800;
    color: #FF8C00;
    letter-spacing: 0.5px;
}}

#topbar .brand span {{ color: #FFD700; font-weight: 400; font-size: 12px; margin-left: 8px; }}

.stats-pills {{
    display: flex;
    gap: 10px;
}}

.pill {{
    padding: 4px 14px;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 600;
    background: #1f1f1f;
    border: 1px solid #333;
}}

.pill.nodes {{ color: #FF8C00; border-color: #FF8C00; }}
.pill.edges {{ color: #FFD700; border-color: #FFD700; }}

#legend {{
    display: flex;
    gap: 16px;
    font-size: 11px;
    color: #888;
    align-items: center;
}}

.legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 4px;
}}

.legend-dot.node {{ background: #FF8C00; box-shadow: 0 0 6px rgba(255,140,0,0.4); }}
.legend-dot.edge {{ background: #FFD700; opacity: 0.5; }}

#graph-container {{
    flex: 1;
    position: relative;
}}

#empty-state {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    color: #555;
    pointer-events: none;
    display: none;
}}

#search-box {{
    position: absolute;
    top: 14px;
    left: 14px;
    z-index: 10;
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 6px 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: border-color 0.2s;
}}

#search-box:focus-within {{
    border-color: #FF8C00;
}}

#search-box input {{
    background: none;
    border: none;
    outline: none;
    color: #FFD700;
    font-size: 13px;
    width: 160px;
}}

#search-box input::placeholder {{ color: #555; }}

#search-box .icon {{ color: #888; font-size: 14px; }}

#hint-text {{
    position: absolute;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 12px;
    color: #444;
    pointer-events: none;
}}

#hint-text span {{ color: #FF8C00; }}

::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: #0d0d0d; }}
::-webkit-scrollbar-thumb {{ background: #333; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #FF8C00; }}

#toast {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #FF8C00;
    color: #000;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    opacity: 0;
    transition: opacity 0.3s;
    z-index: 100;
    pointer-events: none;
}}

#toast.show {{ opacity: 1; }}
</style>
</head>
<body>

<div id="main-area">
    <div id="topbar">
        <div class="brand">TOPOLOGY MAPPER<span>| dependency graph</span></div>
        <div class="stats-pills">
            <div class="pill nodes">NODES: {node_count}</div>
            <div class="pill edges">EDGES: {edge_count}</div>
        </div>
        <div id="legend">
            <span><span class="legend-dot node"></span> Service</span>
            <span><span class="legend-dot edge"></span> Call</span>
        </div>
    </div>

    <div id="graph-container">
        <div id="search-box">
            <span class="icon">&#x1F50D;</span>
            <input type="text" id="search-input" placeholder="Search services..." autocomplete="off">
        </div>
        <div id="hint-text">CLICK a node for details &bull; <span>DRAG</span> to rearrange &bull; <span>SCROLL</span> to zoom</div>
    </div>
</div>

<div id="sidebar">
    <div id="sidebar-header">
        <h2 id="sidebar-title">SERVICE DETAILS</h2>
        <button id="close-btn" onclick="closeSidebar()">&#x2715;</button>
    </div>
    <div id="sidebar-body"></div>
</div>

<div id="toast"></div>

<script>
var nodes = new vis.DataSet({nodes_json});
var edges = new vis.DataSet({edges_json});

var container = document.getElementById('graph-container');
var data = {{ nodes: nodes, edges: edges }};

var options = {{
    autoResize: true,
    nodes: {{
        shape: 'dot',
        borderWidth: 2,
        borderWidthSelected: 3,
        color: {{
            background: '#FF8C00',
            border: '#CC7000',
            highlight: {{ background: '#FFa040', border: '#FFD700' }},
            hover: {{ background: '#FF9d20', border: '#FFD700' }}
        }},
        font: {{
            color: '#FFD700',
            face: 'Inter, system-ui, sans-serif',
            size: 13,
            strokeWidth: 0,
            align: 'center'
        }},
        shadow: {{
            enabled: true,
            color: 'rgba(255,140,0,0.25)',
            size: 12,
            x: 0,
            y: 0
        }},
        scaling: {{ min: 18, max: 55, label: {{ enabled: true, min: 11, max: 16 }} }},
        mass: 2
    }},
    edges: {{
        color: {{
            color: 'rgba(255,140,0,0.25)',
            highlight: '#FFD700',
            hover: '#FF8C00'
        }},
        smooth: {{ type: 'curvedCW', roundness: 0.15 }},
        arrows: {{ to: {{ enabled: true, scaleFactor: 0.6 }} }},
        width: 2,
        selectionWidth: 3,
        hoverWidth: 1.5
    }},
    physics: {{
        barnesHut: {{
            gravitationalConstant: -3500,
            centralGravity: 0.25,
            springLength: 200,
            springConstant: 0.03,
            damping: 0.12,
            avoidOverlap: 0.3
        }},
        minVelocity: 0.75,
        solver: 'barnesHut',
        stabilization: {{ iterations: 300, updateInterval: 20 }}
    }},
    interaction: {{
        hover: true,
        hoverConnectedEdges: true,
        selectConnectedEdges: true,
        navigationButtons: true,
        keyboard: {{ enabled: true, bindToWindow: false }},
        zoomView: true,
        dragView: true,
        tooltipDelay: 150
    }},
    layout: {{ improvedLayout: true }}
}};

var network = new vis.Network(container, data, options);
var allNodes = nodes.get();
var nodeMap = {{}};
allNodes.forEach(function(n) {{ nodeMap[n.id] = n; }});

function showToast(msg) {{
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(function() {{ t.classList.remove('show'); }}, 2000);
}}

function formatMs(ms) {{
    if (ms == null) return '--';
    if (ms >= 1000) return (ms/1000).toFixed(1) + 's';
    return ms.toFixed(1) + 'ms';
}}

function openSidebar(nodeData) {{
    var sidebar = document.getElementById('sidebar');
    var title = document.getElementById('sidebar-title');
    var body = document.getElementById('sidebar-body');

    title.textContent = nodeData.label.toUpperCase();
    var s = nodeData.status || 'healthy';
    var badgeClass = s.toLowerCase();

    var preHTML = '';
    if (nodeData.predecessors && nodeData.predecessors.length > 0) {{
        preHTML = nodeData.predecessors.map(function(p) {{
            return '<li onclick="focusNode(\\'' + p + '\\')">&#x2190; ' + p + '</li>';
        }}).join('');
    }}

    var succHTML = '';
    if (nodeData.successors && nodeData.successors.length > 0) {{
        succHTML = nodeData.successors.map(function(s) {{
            return '<li onclick="focusNode(\\'' + s + '\\')">' + s + ' &#x2192;</li>';
        }}).join('');
    }}

    body.innerHTML = `
        <div class="section">
            <div class="section-title">Status</div>
            <div style="margin-bottom:10px;">
                <span class="status-badge ${{badgeClass}}">${{badgeClass}}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Metrics</div>
            <div class="stat-row"><span class="label">Total Spans</span><span class="value">${{nodeData.total_spans}}</span></div>
            <div class="stat-row"><span class="label">Anomalous</span><span class="value">${{nodeData.anomalous_spans}}</span></div>
            <div class="stat-row"><span class="label">Score</span><span class="value">${{nodeData.score}}</span></div>
            <div class="stat-row"><span class="label">P95 Baseline</span><span class="value">${{formatMs(nodeData.p95_baseline_ms)}}</span></div>
        </div>

        <div class="section">
            <div class="section-title">Connections</div>
            <div class="stat-row"><span class="label">Total Degree</span><span class="value">${{nodeData.degree}}</span></div>
            <div class="stat-row"><span class="label">In-Degree</span><span class="value">${{nodeData.in_degree}}</span></div>
            <div class="stat-row"><span class="label">Out-Degree</span><span class="value">${{nodeData.out_degree}}</span></div>
        </div>

        <div class="section">
            <div class="section-title">Latency Profile</div>
            <div class="stat-row"><span class="label">P95 Inbound</span><span class="value">${{formatMs(nodeData.p95_in_ms)}}</span></div>
            <div class="stat-row"><span class="label">P95 Outbound</span><span class="value">${{formatMs(nodeData.p95_out_ms)}}</span></div>
        </div>

        <div class="section">
            <div class="section-title">Called By</div>
            <ul class="edge-list">${{preHTML || '<li style="color:#555;">none</li>'}}</ul>
        </div>

        <div class="section">
            <div class="section-title">Calls To</div>
            <ul class="edge-list">${{succHTML || '<li style="color:#555;">none</li>'}}</ul>
        </div>
    `;

    sidebar.classList.add('open');
}}

function openEdgeSidebar(edgeData) {{
    var sidebar = document.getElementById('sidebar');
    var title = document.getElementById('sidebar-title');
    var body = document.getElementById('sidebar-body');

    title.textContent = edgeData.from + ' → ' + edgeData.to;

    body.innerHTML = `
        <div class="section">
            <div class="section-title">Edge Details</div>
            <div style="font-size:32px; text-align:center; color:#FFD700; padding:12px 0;">${{edgeData.from}} &rarr; ${{edgeData.to}}</div>
        </div>

        <div class="section">
            <div class="section-title">Traffic</div>
            <div class="stat-row"><span class="label">Total Calls</span><span class="value">${{edgeData.weight}}</span></div>
        </div>

        <div class="section">
            <div class="section-title">Latency Distribution</div>
            <div class="stat-row"><span class="label">Avg</span><span class="value">${{formatMs(edgeData.avg_ms)}}</span></div>
            <div class="stat-row"><span class="label">P50</span><span class="value">${{formatMs(edgeData.p50_ms)}}</span></div>
            <div class="stat-row"><span class="label">P99</span><span class="value">${{formatMs(edgeData.p99_ms)}}</span></div>
            <div class="stat-row"><span class="label">Min</span><span class="value">${{formatMs(edgeData.min_ms)}}</span></div>
            <div class="stat-row"><span class="label">Max</span><span class="value">${{formatMs(edgeData.max_ms)}}</span></div>
        </div>

        <div class="section">
            <div class="section-title">Causal Window</div>
            <div class="stat-row"><span class="label">Lag Window</span><span class="value">${{edgeData.lag_minutes ? edgeData.lag_minutes + ' min' : '--'}}</span></div>
        </div>
    `;

    sidebar.classList.add('open');
}}

function closeSidebar() {{
    document.getElementById('sidebar').classList.remove('open');
}}

function focusNode(nodeId) {{
    network.selectNodes([nodeId]);
    network.focus(nodeId, {{ scale: 1.2, animation: {{ duration: 400, easingFunction: 'easeInOutQuad' }} }});
    var nodeData = nodeMap[nodeId];
    if (nodeData) openSidebar(nodeData);
}}

network.on('selectNode', function(params) {{
    var nodeId = params.nodes[0];
    var nodeData = nodeMap[nodeId];
    if (nodeData) openSidebar(nodeData);
}});

network.on('deselectNode', function(params) {{
    closeSidebar();
}});

network.on('selectEdge', function(params) {{
    var edgeId = params.edges[0];
    var edgeData = edges.get(edgeId);
    if (edgeData) openEdgeSidebar(edgeData);
}});

network.on('deselectEdge', function(params) {{
    closeSidebar();
}});

network.on('doubleClick', function(params) {{
    if (params.nodes.length === 1) {{
        var nodeId = params.nodes[0];
        network.focus(nodeId, {{ scale: 1.5, animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }} }});
        showToast('Zoomed to ' + nodeId);
    }}
}});

network.on('stabilizationIterationsDone', function() {{
    network.setOptions({{ physics: {{ stabilization: false }} }});
    network.fit({{ animation: {{ duration: 1000, easingFunction: 'easeInOutQuad' }} }});
}});

var searchInput = document.getElementById('search-input');
var searchTimeout;
searchInput.addEventListener('input', function() {{
    clearTimeout(searchTimeout);
    var query = this.value.toLowerCase().trim();
    searchTimeout = setTimeout(function() {{
        if (!query) {{
            network.selectNodes([]);
            closeSidebar();
            return;
        }}
        var matched = allNodes.filter(function(n) {{
            return n.label.toLowerCase().includes(query);
        }}).map(function(n) {{ return n.id; }});
        if (matched.length > 0) {{
            network.selectNodes([matched[0]]);
            network.focus(matched[0], {{ scale: 1.3, animation: true }});
            openSidebar(nodeMap[matched[0]]);
        }}
    }}, 200);
}});

searchInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
        this.value = '';
        network.selectNodes([]);
        closeSidebar();
        network.fit({{ animation: true }});
    }}
}});

document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
        closeSidebar();
        network.selectNodes([]);
    }}
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {{
        e.preventDefault();
        document.getElementById('search-input').focus();
    }}
    if ((e.ctrlKey || e.metaKey) && e.key === '0') {{
        e.preventDefault();
        network.fit({{ animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }} }});
        showToast('Fit to view');
    }}
}});

</script>
</body>
</html>"""
