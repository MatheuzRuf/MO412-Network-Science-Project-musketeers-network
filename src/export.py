"""
Persist graphs (GraphML + JSON) and metrics CSV.
"""
import csv
import json
import logging

import networkx as nx
from networkx.readwrite import json_graph

from src.config import GRAPHS_DIR, METRICS_CSV

logger = logging.getLogger(__name__)


def save_graph(win_id: str, G: nx.Graph) -> None:
    """Save graph as GraphML (for Gephi/Cytoscape) and node-link JSON."""
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    graphml_path = GRAPHS_DIR / f"{win_id}.graphml"
    nx.write_graphml(G, str(graphml_path))

    json_path = GRAPHS_DIR / f"{win_id}.json"
    data = json_graph.node_link_data(G)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(
        "Saved graph %s  (%d nodes, %d edges)",
        win_id, G.number_of_nodes(), G.number_of_edges(),
    )


def save_metrics(records: list[dict]) -> None:
    """Append window metrics to the CSV (creates file if absent)."""
    if not records:
        return
    METRICS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames   = list(records[0].keys())
    write_header = not METRICS_CSV.exists()
    with open(METRICS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(records)
