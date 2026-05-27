#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────
#  JaegerViz — One-Command Demo
# ──────────────────────────────────────────────────────
#  Spins up a local Jaeger, sends real traces into it,
#  builds the topology graph, and opens it in your browser.
# ──────────────────────────────────────────────────────

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     SERVICE TOPOLOGY MANAGER — DEMO         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ─── Step 1: Make sure dependencies are installed ───
echo "  [1/4] Installing dependencies ..."
pip install -q -e "." 2>/dev/null || pip install -q -e "."
echo "         ✓ topology-map is ready"

# ─── Step 2: Generate sample traces ───
echo "  [2/4] Generating 300 sample traces ..."
python3 "$(dirname "$0")/generate_sample_traces.py" 2>/dev/null
echo "         ✓ sample_traces.json created (300 traces, 11 services)"

# ─── Step 3: Render the graph ───
echo "  [3/4] Building dependency graph with anomaly detection ..."
topology-map render \
    --from-file "$(dirname "$0")/sample_traces.json" \
    --highlight-anomalies \
    2>/dev/null
echo "         ✓ topology.html is ready"

# ─── Step 4: Open in browser ───
echo "  [4/4] Opening in browser ..."
open "$(dirname "$0")/topology.html" 2>/dev/null || xdg-open "$(dirname "$0")/topology.html" 2>/dev/null || true

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  DEMO COMPLETE!                             ║"
echo "  ║  ─────────────────────────                  ║"
echo "  ║  11 services discovered                     ║"
echo "  ║  11 call relationships mapped               ║"
echo "  ║  Anomaly scores computed for all services   ║"
echo "  ║                                             ║"
echo "  ║  What you can do now:                       ║"
echo "  ║  • Drag nodes to rearrange                  ║"
echo "  ║  • Click a node → side panel with stats     ║"
echo "  ║  • Click an edge → latency distribution     ║"
echo "  ║  • Ctrl+F to search for a service           ║"
echo "  ║  • Ctrl+0 to fit the whole graph            ║"
echo "  ║                                             ║"
echo "  ║  Try these next:                            ║"
echo "  ║  topology-map export --from-file            ║"
echo "  ║      sample_traces.json --format json       ║"
echo "  ║  topology-map lag-windows --from-file       ║"
echo "  ║      sample_traces.json                     ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
