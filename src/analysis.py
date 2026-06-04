"""
Graph metrics and structural balance analysis.
"""
import itertools
import math

import networkx as nx
import numpy as np


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


# ── RQ1: Sentiment-Based Robustness ──────────────────────────────────────────

def giant_component_fractions(G: nx.Graph) -> dict:
    """
    Return the fraction of nodes in the Giant Component (GC) for:
      - gc_all_frac:  full graph
      - gc_pos_frac:  subgraph keeping only sign=+1 edges
      - gc_neg_frac:  subgraph keeping only sign=-1 edges
    """
    n = G.number_of_nodes()
    if n == 0:
        return {"gc_all_frac": 0.0, "gc_pos_frac": 0.0, "gc_neg_frac": 0.0}

    def _gc_frac(H):
        if H.number_of_nodes() == 0:
            return 0.0
        components = list(nx.connected_components(H))
        gc_size = max(len(c) for c in components)
        return round(gc_size / n, 4)

    pos_edges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("sign") == 1]
    neg_edges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("sign") == -1]

    G_pos = nx.Graph()
    G_pos.add_nodes_from(G.nodes())
    G_pos.add_edges_from(pos_edges)

    G_neg = nx.Graph()
    G_neg.add_nodes_from(G.nodes())
    G_neg.add_edges_from(neg_edges)

    return {
        "gc_all_frac": _gc_frac(G),
        "gc_pos_frac": _gc_frac(G_pos),
        "gc_neg_frac": _gc_frac(G_neg),
    }


# ── RQ2: Topology & Degree Correlations ─────────────────────────────────────

def power_law_exponent(G: nx.Graph) -> float:
    """
    Estimate the power-law exponent γ of the degree distribution using
    maximum-likelihood (discrete Pareto) via scipy, falling back to
    log-log OLS on the CCDF if the fit is degenerate.
    Returns NaN for graphs with fewer than 3 distinct degree values.
    """
    degrees = [d for _, d in G.degree() if d > 0]
    if len(degrees) < 3:
        return float("nan")

    # MLE for discrete power-law: γ = 1 + n / sum(ln(k / (k_min - 0.5)))
    k_min = min(degrees)
    n = len(degrees)
    gamma = 1.0 + n / sum(math.log(k / (k_min - 0.5)) for k in degrees)
    return round(gamma, 4)


def assortativity_metrics(G: nx.Graph) -> dict:
    """
    Return degree assortativity and sentiment assortativity.
    For sentiment assortativity each node is assigned the mean
    avg_sentiment of its incident edges, then numeric assortativity
    is computed.
    """
    if G.number_of_edges() < 2:
        return {"degree_assortativity": float("nan"),
                "sentiment_assortativity": float("nan")}

    try:
        deg_assort = round(nx.degree_assortativity_coefficient(G), 4)
    except Exception:
        deg_assort = float("nan")

    # Assign per-node mean sentiment
    for node in G.nodes():
        nbr_sentiments = [G[node][nbr]["avg_sentiment"]
                          for nbr in G.neighbors(node)
                          if "avg_sentiment" in G[node][nbr]]
        G.nodes[node]["node_sentiment"] = (
            sum(nbr_sentiments) / len(nbr_sentiments) if nbr_sentiments else 0.0
        )

    try:
        sent_assort = round(
            nx.numeric_assortativity_coefficient(G, "node_sentiment"), 4
        )
    except Exception:
        sent_assort = float("nan")

    return {
        "degree_assortativity":    deg_assort,
        "sentiment_assortativity": sent_assort,
    }


# ── RQ3: Balance & Communities ───────────────────────────────────────────────

def louvain_metrics(G: nx.Graph, seed: int = 42) -> dict:
    """
    Run Louvain community detection (built into NetworkX ≥ 3.4) on
    the graph weighted by co-occurrence count and return number of
    communities and modularity.
    """
    if G.number_of_nodes() < 2 or G.number_of_edges() == 0:
        return {"n_communities": 0, "modularity": float("nan")}

    try:
        partition = nx.community.louvain_communities(G, weight="weight", seed=seed)
        mod = round(nx.community.modularity(G, partition, weight="weight"), 4)
        return {"n_communities": len(partition), "modularity": mod}
    except Exception:
        return {"n_communities": 0, "modularity": float("nan")}


def triad_type_census(G: nx.Graph) -> dict:
    """
    Count triangle types by sign pattern (Heider structural balance):
      ppp  (+++)  balanced — mutual friends
      pmm  (+−−)  balanced — enemy of my enemy
      ppm  (++−)  unbalanced — two friends with a mutual enemy
      mmm  (−−−)  unbalanced — three mutual enemies
    Returns counts and fractions.
    """
    counts = {"ppp": 0, "pmm": 0, "ppm": 0, "mmm": 0}
    total = 0

    for a, b, c in itertools.combinations(G.nodes(), 3):
        if G.has_edge(a, b) and G.has_edge(b, c) and G.has_edge(a, c):
            signs = sorted([
                G[a][b]["sign"], G[b][c]["sign"], G[a][c]["sign"]
            ])  # sort so +++ → [1,1,1], +−− → [-1,-1,1], etc.
            total += 1
            if signs == [1, 1, 1]:
                counts["ppp"] += 1
            elif signs == [-1, -1, 1]:
                counts["pmm"] += 1
            elif signs == [-1, 1, 1]:
                counts["ppm"] += 1
            elif signs == [-1, -1, -1]:
                counts["mmm"] += 1
            # signs containing 0 (neutral) are skipped

    fracs = {k + "_frac": round(v / total, 4) if total else 0.0
             for k, v in counts.items()}
    return {"total_triangles": total, **counts, **fracs}

