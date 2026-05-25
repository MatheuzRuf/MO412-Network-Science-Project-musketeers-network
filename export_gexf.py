#!/usr/bin/env python3
"""
Export all rolling-window graphs to a single dynamic GEXF file
for Gephi's Timeline feature.

Each window gets a sequential time step (0 = book_1_w001_010 … 369 = book_6 last).
In Gephi: Appearance panel → Colour by avg_sentiment or sign;
          Timeline panel → play to animate the progression.
"""

import re
from pathlib import Path
from xml.etree import ElementTree as ET

import networkx as nx

# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).parent
GRAPHS_DIR = BASE_DIR / "outputs" / "graphs"
OUT_FILE   = BASE_DIR / "outputs" / "trilogy_dynamic.gexf"
MAP_FILE   = BASE_DIR / "outputs" / "window_timestep_map.txt"
# ---------------------------------------------------------------------------


def _sort_key(path: Path) -> tuple[int, int]:
    m = re.match(r"book_(\d+)_w(\d+)_\d+\.graphml", path.name)
    if not m:
        return (99, 0)
    return (int(m.group(1)), int(m.group(2)))


def load_windows() -> list[tuple[str, nx.Graph]]:
    files = sorted(GRAPHS_DIR.glob("*.graphml"), key=_sort_key)
    result = []
    for f in files:
        G = nx.read_graphml(f)
        result.append((f.stem, G))
    return result


def build_gexf(windows: list[tuple[str, nx.Graph]]) -> ET.Element:
    root = ET.Element("gexf", {
        "xmlns":     "http://gexf.net/1.2",
        "xmlns:viz": "http://gexf.net/1.2/viz",
        "version":   "1.2",
    })

    meta = ET.SubElement(root, "meta", {"lastmodifieddate": "2026-05-25"})
    ET.SubElement(meta, "creator").text   = "pc-pipeline"
    ET.SubElement(meta, "description").text = (
        "Three Musketeers Trilogy – 370 rolling-window signed social network"
    )

    graph = ET.SubElement(root, "graph", {
        "defaultedgetype": "undirected",
        "mode":            "dynamic",
        "timeformat":      "integer",
    })

    # ── edge attributes (dynamic) ──────────────────────────────────────────
    ea = ET.SubElement(graph, "attributes", {"class": "edge", "mode": "dynamic"})
    ET.SubElement(ea, "attribute", {"id": "weight",        "title": "weight",        "type": "integer"})
    ET.SubElement(ea, "attribute", {"id": "avg_sentiment", "title": "avg_sentiment", "type": "float"})
    ET.SubElement(ea, "attribute", {"id": "sign",          "title": "sign",          "type": "integer"})

    # ── node attributes (static) ───────────────────────────────────────────
    na = ET.SubElement(graph, "attributes", {"class": "node", "mode": "static"})
    ET.SubElement(na, "attribute", {"id": "first_book", "title": "first_book", "type": "integer"})

    # ── accumulate spells ─────────────────────────────────────────────────
    # node_data  : {node_id: {"spells": [(start,end)], "first_book": int}}
    # edge_data  : {(src,tgt): [(t, weight, sentiment, sign)]}
    node_data: dict[str, dict] = {}
    edge_data: dict[tuple[str,str], list] = {}

    for t, (win_id, G) in enumerate(windows):
        book_num = int(re.match(r"book_(\d+)_", win_id).group(1))

        for node in G.nodes():
            nid = str(node)
            if nid not in node_data:
                node_data[nid] = {"spells": [], "first_book": book_num}
            node_data[nid]["spells"].append((t, t + 1))

        for u, v, data in G.edges(data=True):
            us, vs = str(u), str(v)
            key = (us, vs) if us <= vs else (vs, us)
            if key not in edge_data:
                edge_data[key] = []
            edge_data[key].append((
                t,
                int(data.get("weight", 1)),
                float(data.get("avg_sentiment", 0.0)),
                int(data.get("sign", 1)),
            ))

    # ── write nodes ───────────────────────────────────────────────────────
    nodes_el = ET.SubElement(graph, "nodes")
    for nid, info in sorted(node_data.items()):
        node_el = ET.SubElement(nodes_el, "node", {"id": nid, "label": nid.title()})
        # static attribute
        avs = ET.SubElement(node_el, "attvalues")
        ET.SubElement(avs, "attvalue", {"for": "first_book", "value": str(info["first_book"])})
        # spells
        sp_el = ET.SubElement(node_el, "spells")
        for start, end in info["spells"]:
            ET.SubElement(sp_el, "spell", {"start": str(start), "end": str(end)})

    # ── write edges ───────────────────────────────────────────────────────
    edges_el = ET.SubElement(graph, "edges")
    for eid, ((src, tgt), occurrences) in enumerate(sorted(edge_data.items())):
        edge_el = ET.SubElement(edges_el, "edge", {
            "id":     str(eid),
            "source": src,
            "target": tgt,
        })
        sp_el  = ET.SubElement(edge_el, "spells")
        avs_el = ET.SubElement(edge_el, "attvalues")
        for (t, weight, sentiment, sign) in occurrences:
            s, e = str(t), str(t + 1)
            ET.SubElement(sp_el, "spell", {"start": s, "end": e})
            ET.SubElement(avs_el, "attvalue", {"for": "weight",        "value": str(weight),          "start": s, "end": e})
            ET.SubElement(avs_el, "attvalue", {"for": "avg_sentiment", "value": f"{sentiment:.4f}",   "start": s, "end": e})
            ET.SubElement(avs_el, "attvalue", {"for": "sign",          "value": str(sign),            "start": s, "end": e})

    return root


def write_timestep_map(windows: list[tuple[str, nx.Graph]]) -> None:
    lines = ["t\twin_id\tbook"]
    for t, (win_id, _) in enumerate(windows):
        book = re.match(r"(book_\d+)_", win_id).group(1)
        lines.append(f"{t}\t{win_id}\t{book}")
    MAP_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Time-step map → {MAP_FILE}")


def main() -> None:
    print("Loading windows …")
    windows = load_windows()
    print(f"  {len(windows)} windows loaded")

    write_timestep_map(windows)

    print("Building dynamic GEXF …")
    root = build_gexf(windows)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")   # Python 3.9+
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUT_FILE, encoding="utf-8", xml_declaration=True)

    size_mb = OUT_FILE.stat().st_size / 1_048_576
    print(f"  Written → {OUT_FILE}  ({size_mb:.1f} MB)")
    print()
    print("Book time ranges:")
    from collections import defaultdict
    by_book: dict[str, list[int]] = defaultdict(list)
    for t, (win_id, _) in enumerate(windows):
        book = re.match(r"(book_\d+)_", win_id).group(1)
        by_book[book].append(t)
    for book, ts in sorted(by_book.items()):
        print(f"  {book}: t={ts[0]}–{ts[-1]}  ({len(ts)} windows)")
    print()
    print("Gephi quick-start:")
    print("  1. File → Open → trilogy_dynamic.gexf")
    print("  2. Layout: ForceAtlas 2  (run ~30 s, then stop)")
    print("  3. Appearance → Nodes → Colour → Partition → first_book")
    print("  4. Appearance → Edges → Colour → Ranking → avg_sentiment  (red=-1 … green=+1)")
    print("  5. Timeline panel (bottom) → Enable → press Play")
    print("  6. Screen-record the canvas while Timeline plays")


if __name__ == "__main__":
    main()
