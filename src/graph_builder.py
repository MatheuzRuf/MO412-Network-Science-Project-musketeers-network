"""
Build signed, weighted character interaction graphs.
"""
import networkx as nx
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def _sentiment(text: str) -> float:
    """Return VADER compound score in the range [-1.0, 1.0]."""
    return _analyzer.polarity_scores(text)["compound"]


def build_graph(scenes: list[dict], text: str) -> nx.Graph:
    """
    Build an undirected signed graph from validated scenes.

    Edge attributes
    ---------------
    weight          : number of shared scenes
    sentiment_sum   : cumulative VADER compound score
    avg_sentiment   : sentiment_sum / weight
    sign            : +1 (positive), -1 (negative), 0 (neutral)
    """
    G: nx.Graph = nx.Graph()

    for scene in scenes:
        snippet = text[scene["start_char"]: scene["end_char"]]
        score   = _sentiment(snippet)
        chars   = scene["characters"]

        for i in range(len(chars)):
            for j in range(i + 1, len(chars)):
                u, v = chars[i], chars[j]
                if G.has_edge(u, v):
                    G[u][v]["weight"]        += 1
                    G[u][v]["sentiment_sum"] += score
                else:
                    G.add_edge(u, v, weight=1, sentiment_sum=score)

    for u, v in G.edges():
        avg = G[u][v]["sentiment_sum"] / G[u][v]["weight"]
        G[u][v]["avg_sentiment"] = round(avg, 6)
        G[u][v]["sign"] = 1 if avg > 0 else (-1 if avg < 0 else 0)

    return G
