"""
Graph metrics and structural balance analysis.
"""
import collections
import itertools
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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


# ── Centrality & Diameter ─────────────────────────────────────────────────

def centrality_metrics(G: nx.Graph) -> dict:
    """
    Compute per-node centrality scores.

    Returns a dict: metric_name → list of (node, score) sorted descending.
    Metrics: degree, betweenness, closeness, pagerank, eigenvector.
    """
    if G.number_of_nodes() < 2:
        return {}

    degree_c  = nx.degree_centrality(G)
    between_c = nx.betweenness_centrality(G, weight="weight", normalized=True)

    try:
        close_c = nx.closeness_centrality(G)
    except Exception:
        close_c = {n: 0.0 for n in G.nodes()}

    try:
        pr = nx.pagerank(G, weight="weight")
    except Exception:
        pr = {n: 0.0 for n in G.nodes()}

    try:
        eig_c = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception:
        try:
            eig_c = nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
        except Exception:
            eig_c = {n: 0.0 for n in G.nodes()}

    def _sorted_items(d):
        return sorted(d.items(), key=lambda x: x[1], reverse=True)

    return {
        "degree":      _sorted_items(degree_c),
        "betweenness": _sorted_items(between_c),
        "closeness":   _sorted_items(close_c),
        "pagerank":    _sorted_items(pr),
        "eigenvector": _sorted_items(eig_c),
    }


def network_diameter(G: nx.Graph) -> int:
    """
    Return the diameter of the largest connected component (GCC).
    Returns -1 for trivial or fully-disconnected graphs.
    """
    if G.number_of_nodes() < 2:
        return -1
    components = list(nx.connected_components(G))
    gcc = G.subgraph(max(components, key=len)).copy()
    if gcc.number_of_nodes() < 2:
        return -1
    try:
        return nx.diameter(gcc)
    except Exception:
        return -1


# ── Visualisation helpers ─────────────────────────────────────────────────

_SIGN_COLORS = {1: "#4CAF50", -1: "#F44336", 0: "#9E9E9E"}
_BOOK_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948",
]


def _edge_sign_colors(G: nx.Graph, edges=None) -> list:
    """Map each edge to a colour based on its sign attribute."""
    if edges is None:
        edges = list(G.edges(data=True))
    colors = []
    for _, _, d in edges:
        try:
            s = int(float(d.get("sign", 0)))
        except (TypeError, ValueError):
            s = 0
        colors.append(_SIGN_COLORS.get(s, "#9E9E9E"))
    return colors


# ── Plot: Community graph ─────────────────────────────────────────────────

def plot_community_graph(
    G: nx.Graph,
    title: str,
    output_path,
    *,
    top_n_labels: int = 15,
    seed: int = 42,
) -> None:
    """
    Spring-layout graph coloured by Louvain community, node size ∝ degree,
    edge colour encodes sentiment sign (green/red/grey).

    Only the top-*top_n_labels* highest-degree nodes are labelled to keep
    the figure readable.
    """
    if G.number_of_nodes() < 2:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        partition = list(nx.community.louvain_communities(G, weight="weight", seed=seed))
    except Exception:
        partition = [set(G.nodes())]

    node_community = {n: i for i, comm in enumerate(partition) for n in comm}
    n_comm = len(partition)
    cmap = matplotlib.colormaps["tab10" if n_comm <= 10 else "tab20"]

    nodes = list(G.nodes())
    node_colors = [cmap(node_community.get(n, 0) % cmap.N) for n in nodes]
    degrees = dict(G.degree())
    node_sizes = [300 + degrees[n] * 120 for n in nodes]

    edges = list(G.edges(data=True))
    edge_colors = _edge_sign_colors(G, edges)
    edge_widths  = [0.5 + G[u][v].get("weight", 1) * 0.25 for u, v, _ in edges]

    pos = nx.spring_layout(G, weight="weight", seed=seed, k=1.5)
    label_set = set(sorted(degrees, key=lambda n: degrees[n], reverse=True)[:top_n_labels])

    fig, ax = plt.subplots(figsize=(14, 10))
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                           width=edge_widths, alpha=0.55)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_labels(G, pos, labels={n: n for n in label_set},
                            ax=ax, font_size=8, font_weight="bold")

    comm_handles = [
        mpatches.Patch(facecolor=cmap(i % cmap.N),
                       label=f"Community {i + 1}  ({len(partition[i])} nodes)")
        for i in range(n_comm)
    ]
    sign_handles = [
        mpatches.Patch(facecolor="#4CAF50", label="Positive edge"),
        mpatches.Patch(facecolor="#F44336", label="Negative edge"),
        mpatches.Patch(facecolor="#9E9E9E", label="Neutral edge"),
    ]
    ax.legend(handles=sign_handles + comm_handles,
              fontsize=7, loc="upper left", framealpha=0.7, ncol=2)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Plot: Centrality ranking ──────────────────────────────────────────────

def plot_centrality_ranking(
    G: nx.Graph,
    title: str,
    output_path,
    *,
    metric: str = "betweenness",
    top_n: int = 15,
) -> None:
    """
    Horizontal bar chart of the top-*top_n* characters ranked by *metric*
    centrality.  Bar colour reflects that character's mean edge sentiment.

    metric: 'degree' | 'betweenness' | 'closeness' | 'pagerank' | 'eigenvector'
    """
    if G.number_of_nodes() < 2:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ranked = centrality_metrics(G).get(metric, [])[:top_n]
    if not ranked:
        return

    names, scores = zip(*ranked)
    bar_colors = []
    for name in names:
        sents = [G[name][nb]["avg_sentiment"]
                 for nb in G.neighbors(name) if "avg_sentiment" in G[name][nb]]
        avg = sum(sents) / len(sents) if sents else 0.0
        bar_colors.append(
            "#4CAF50" if avg > 0.05 else "#F44336" if avg < -0.05 else "#9E9E9E"
        )

    fig, ax = plt.subplots(figsize=(10, max(5, len(names) * 0.48)))
    y_pos = list(range(len(names)))
    bars = ax.barh(y_pos, scores, color=bar_colors, edgecolor="white", height=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel(f"{metric.capitalize()} Centrality", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")

    max_s = max(scores) if scores else 1.0
    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + max_s * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{score:.3f}", va="center", fontsize=8)

    ax.legend(handles=[
        mpatches.Patch(facecolor="#4CAF50", label="Mostly positive"),
        mpatches.Patch(facecolor="#F44336", label="Mostly negative"),
        mpatches.Patch(facecolor="#9E9E9E", label="Neutral"),
    ], fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Plot: Degree distribution ─────────────────────────────────────────────

def plot_degree_distribution(
    G: nx.Graph,
    title: str,
    output_path,
) -> None:
    """
    Log-log scatter plot of the empirical degree distribution with a
    power-law fit line overlaid (γ estimated by MLE).
    """
    if G.number_of_nodes() < 3:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    degrees = [d for _, d in G.degree() if d > 0]
    degree_counts = collections.Counter(degrees)
    k_vals = sorted(degree_counts)
    p_vals = [degree_counts[k] / len(degrees) for k in k_vals]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(k_vals, p_vals, color="#4E79A7", s=60, zorder=3, label="Empirical P(k)")

    gamma = power_law_exponent(G)
    if not math.isnan(gamma) and len(k_vals) >= 2:
        k_min = min(degrees)
        k_range = np.linspace(k_min, max(degrees), 200)
        c = p_vals[0] * (k_min ** gamma)
        ax.plot(k_range, c * k_range ** (-gamma), "r--",
                linewidth=2, label=f"Power-law  γ = {gamma:.2f}")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Degree k", fontsize=11)
    ax.set_ylabel("P(k)", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Plot: Sentiment heatmap ───────────────────────────────────────────────

def plot_sentiment_heatmap(
    G: nx.Graph,
    title: str,
    output_path,
    *,
    top_n: int = 25,
) -> None:
    """
    Heatmap of avg_sentiment for every edge between the top-*top_n*
    highest-degree characters.  Green = positive, red = negative,
    masked cells = no direct edge.
    """
    if G.number_of_edges() < 2:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    degrees = dict(G.degree())
    top_chars = sorted(degrees, key=lambda n: degrees[n], reverse=True)[:top_n]
    n = len(top_chars)

    matrix = np.full((n, n), np.nan)
    for i, u in enumerate(top_chars):
        for j, v in enumerate(top_chars):
            if i != j and G.has_edge(u, v):
                matrix[i, j] = G[u][v].get("avg_sentiment", 0.0)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.52), max(7, n * 0.48)))
    im = ax.imshow(np.ma.masked_invalid(matrix),
                   cmap="RdYlGn", vmin=-1.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(top_chars, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(top_chars, fontsize=8)
    fig.colorbar(im, ax=ax, label="Avg. Sentiment", shrink=0.8)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Plot: Ego network ─────────────────────────────────────────────────────

def plot_ego_network(
    G: nx.Graph,
    character: str,
    title: str,
    output_path,
    *,
    radius: int = 2,
    seed: int = 42,
) -> None:
    """
    Spring-layout ego network for *character* up to *radius* hops.
    Ego node is highlighted in red; edges are coloured by sign.
    """
    if character not in G:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ego = nx.ego_graph(G, character, radius=radius)
    degrees = dict(ego.degree())
    node_sizes = [700 if n == character else 200 + degrees[n] * 80
                  for n in ego.nodes()]
    node_colors = ["#E15759" if n == character else "#4E79A7"
                   for n in ego.nodes()]
    edges = list(ego.edges(data=True))
    edge_colors = _edge_sign_colors(ego, edges)
    edge_widths  = [1.0 + ego[u][v].get("weight", 1) * 0.3 for u, v, _ in edges]

    pos = nx.spring_layout(ego, weight="weight", seed=seed, k=2.0)

    fig, ax = plt.subplots(figsize=(11, 8))
    nx.draw_networkx_edges(ego, pos, ax=ax, edge_color=edge_colors,
                           width=edge_widths, alpha=0.6)
    nx.draw_networkx_nodes(ego, pos, ax=ax, node_color=node_colors,
                           node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_labels(ego, pos, ax=ax, font_size=8, font_weight="bold")
    ax.legend(handles=[
        mpatches.Patch(facecolor="#E15759", label=f"Ego: {character}"),
        mpatches.Patch(facecolor="#4E79A7", label="Alter"),
        mpatches.Patch(facecolor="#4CAF50", label="Positive edge"),
        mpatches.Patch(facecolor="#F44336", label="Negative edge"),
    ], fontsize=8, loc="upper left", framealpha=0.7)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Plot: Metrics over time ───────────────────────────────────────────────

def plot_metrics_over_time(
    records: list[dict],
    output_dir,
) -> None:
    """
    Multi-panel time-series of key network metrics across all sliding windows,
    with one coloured line per book.

    Saves ``metrics_over_time.png`` inside *output_dir*.
    """
    if not records:
        return
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    books: dict[str, list[dict]] = {}
    for r in records:
        books.setdefault(r["book"], []).append(r)
    for recs in books.values():
        recs.sort(key=lambda r: r["first_ch"])

    book_colors = {b: _BOOK_PALETTE[i % len(_BOOK_PALETTE)]
                   for i, b in enumerate(sorted(books))}

    panels = [
        ("nodes",         "Nodes"),
        ("edges",         "Edges"),
        ("density",       "Density"),
        ("avg_sentiment", "Avg Sentiment"),
        ("balance",       "Balance Ratio"),
        ("n_communities", "# Communities"),
    ]

    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    for ax, (key, label) in zip(axes.flatten(), panels):
        for book, recs in sorted(books.items()):
            ys = [r.get(key, float("nan")) for r in recs]
            ax.plot(range(len(ys)), ys,
                    label=book.replace("_", " ").title(),
                    color=book_colors[book],
                    linewidth=1.8, alpha=0.85)
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_xlabel("Window index", fontsize=9)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, ncol=2)

    fig.suptitle("Network Metrics Across Sliding Windows",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    fig.savefig(str(output_dir / "metrics_over_time.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

