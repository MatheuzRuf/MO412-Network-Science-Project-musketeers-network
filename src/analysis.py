"""
Graph metrics and structural balance analysis.
"""
import itertools

import networkx as nx


def compute_metrics(G: nx.Graph) -> dict:
    """Return basic graph statistics for one arc."""
    n = G.number_of_nodes()
    if n == 0:
        return {
            "nodes": 0, "edges": 0, "avg_degree": 0.0,
            "density": 0.0, "avg_sentiment": 0.0,
            "positive_edges": 0, "negative_edges": 0,
        }

    degrees      = dict(G.degree())
    avg_degree   = sum(degrees.values()) / n

    sentiments      = [d["avg_sentiment"] for _, _, d in G.edges(data=True)]
    avg_sentiment   = sum(sentiments) / len(sentiments) if sentiments else 0.0
    positive_edges  = sum(1 for s in sentiments if s > 0)
    negative_edges  = sum(1 for s in sentiments if s < 0)

    return {
        "nodes":          n,
        "edges":          G.number_of_edges(),
        "avg_degree":     round(avg_degree,   4),
        "density":        round(nx.density(G), 4),
        "avg_sentiment":  round(avg_sentiment, 4),
        "positive_edges": positive_edges,
        "negative_edges": negative_edges,
    }


def balance_ratio(G: nx.Graph) -> float:
    """
    Structural balance ratio.

    Iterates all node triples that form a triangle and returns the
    fraction whose edge-sign product equals +1 (balanced triangle).
    """
    total_triangles   = 0
    balanced_count    = 0

    for a, b, c in itertools.combinations(G.nodes(), 3):
        if G.has_edge(a, b) and G.has_edge(b, c) and G.has_edge(a, c):
            total_triangles += 1
            sign_product = (
                G[a][b]["sign"] * G[b][c]["sign"] * G[a][c]["sign"]
            )
            if sign_product == 1:
                balanced_count += 1

    return balanced_count / total_triangles if total_triangles else 0.0
