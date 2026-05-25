# Three Musketeers Trilogy — Signed Character-Interaction Networks

A dynamic, signed social-network analysis of Alexandre Dumas's complete *Three Musketeers* trilogy (six books, ~2.5 million words). The pipeline extracts characters from plain text, co-locates them inside rolling scene windows, scores each relationship with VADER sentiment, and produces a time-evolving signed graph suitable for Gephi or further network analysis.

---

## What it does

```
Raw .txt ──► Chapter splitter ──► Character extractor ──► Scene detector
                                                                │
                                                         Co-occurrence
                                                         + VADER sentiment
                                                                │
                                                     Signed NetworkX graph
                                                     (per rolling window)
                                                                │
                              ┌─────────────────┬──────────────┘
                              │                 │
                       outputs/graphs/    outputs/trilogy_dynamic.gexf
                       outputs/metrics.csv
```

**Each time step is one rolling window of 10 chapters with a 1-chapter step.** A window extracts every co-occurring character pair from heuristically detected scenes within it; the edge sentiment is the VADER compound score averaged across all scenes where that pair appears.  Edges are signed: `+1` (positive/neutral) or `−1` (negative).

---

## Project structure

```
.
├── main.py                  # Pipeline entry-point
├── export_gexf.py           # Assembles the dynamic GEXF for Gephi
├── split_books.py           # Utility: split Gutenberg files into chapters
├── requirements.txt
├── src/
│   ├── config.py            # Paths and book registry
│   ├── preprocessing.py     # Text cleaning
│   ├── chapter_parser.py    # Chapter boundary detection
│   ├── characters.py        # Heuristic character extraction + alias/role resolution
│   ├── scenes.py            # Heuristic scene detection (sliding window)
│   ├── graph_builder.py     # Co-occurrence graph + VADER sentiment
│   ├── analysis.py          # Graph metrics + structural balance ratio
│   └── export.py            # JSON / GraphML serialisation
├── data/
│   ├── raw/                 # Input: six Gutenberg .txt files
│   ├── clean/               # Normalised text
│   ├── chapters/            # Per-chapter text files
│   └── cache/               # Intermediate JSON (characters, scenes)
└── outputs/
    ├── graphs/              # 370 per-window JSON graphs
    ├── metrics.csv          # Per-window statistics
    ├── trilogy_dynamic.gexf # Gephi-ready dynamic network (14.6 MB)
    └── window_timestep_map.txt
```

---

## Books covered

| # | Title | Windows (time steps) |
|---|-------|----------------------|
| 1 | *The Three Musketeers* (1844) | t = 0 – 57 (58 steps) |
| 2 | *Twenty Years After* (1845) | t = 58 – 138 (81 steps) |
| 3 | *The Vicomte de Bragelonne* (1847) | t = 139 – 204 (66 steps) |
| 4 | *Ten Years Later* (1848) | t = 205 – 260 (56 steps) |
| 5 | *Louise de la Vallière* (1848) | t = 261 – 318 (58 steps) |
| 6 | *The Man in the Iron Mask* (1850) | t = 319 – 369 (51 steps) |

---

## Results

### Corpus-level

| Metric | Value |
|--------|-------|
| Total time steps (windows) | **370** |
| Unique characters (nodes) | **269** |
| Total edge-instances (across all windows) | **56 631** |
| Avg nodes per window | 23.5 (min 11, max 43) |
| Avg edges per window | 153 (min 37, max 418) |
| Positive edges | 87.1 % |
| Negative edges | 12.9 % |
| Mean edge sentiment | 0.562 |
| Mean structural balance ratio | **0.858** |

Structural balance is defined as the fraction of closed triangles whose edge-sign product is +1 ("the enemy of my enemy is my friend"). A value of 0.858 means 85.8 % of all triangles in the average window satisfy balance theory — well above the random baseline (~0.5).

### Per-book breakdown

| Book | Windows | Avg nodes | Avg edges | Avg sentiment | +edge % | Avg balance |
|------|---------|-----------|-----------|---------------|---------|-------------|
| *The Three Musketeers* | 58 | 22.9 | 152.6 | 0.496 | 83.6 % | 0.820 |
| *Twenty Years After* | 81 | 30.2 | 246.7 | 0.473 | 83.6 % | 0.824 |
| *The Vicomte de Bragelonne* | 66 | 21.2 | 113.6 | 0.630 | 90.6 % | 0.893 |
| *Ten Years Later* | 56 | 22.2 | 147.7 | 0.742 | 95.1 % | 0.930 |
| *Louise de la Vallière* | 58 | 20.4 | 108.5 | 0.660 | 94.1 % | 0.919 |
| *The Man in the Iron Mask* | 51 | 21.1 | 112.5 | 0.381 | 81.0 % | 0.763 |

Notable patterns:
- **Books 4–5** (*Ten Years Later* / *Louise de la Vallière*) are the most positive and most structurally balanced — the court intrigue arc is more courtly than violent.
- **Book 6** (*The Man in the Iron Mask*) drops sharply in sentiment (0.381) and balance (0.763) as key characters die and alliances fracture — the most structurally unstable arc of the trilogy.
- **Book 2** (*Twenty Years After*) has the most complex networks (avg 30.2 nodes, 246.7 edges per window) — the widest cast, reflecting the civil war and dual-front plot.

### Top 20 characters (by number of windows appeared in)

| Rank | Character | Windows |
|------|-----------|---------|
| 1 | Aramis | 274 |
| 2 | Louis (XIV) | 255 |
| 3 | Athos | 246 |
| 4 | Raoul (Vicomte de Bragelonne) | 238 |
| 5 | Porthos | 235 |
| 6 | Mazarin | 221 |
| 7 | Charles (II of England) | 197 |
| 8 | Fouquet | 194 |
| 9 | Fère (Athos's full title) | 183 |
| 10 | Planchet | 179 |
| 11 | Grimaud | 176 |
| 12 | Colbert | 172 |
| 13 | Anne (of Austria) | 164 |
| 14 | Vallière (Louise de la) | 159 |
| 15 | Guiche | 151 |
| 16 | Richelieu | 150 |
| 17 | Henrietta (of England) | 143 |
| 18 | Montalais | 126 |
| 19 | Louise | 120 |
| 20 | Buckingham | 118 |

---

## Setup

```bash
# 1. Clone / unzip; enter project directory
# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place the six Gutenberg plain-text files in data/raw/
#    (filenames must match those in src/config.py)

# 5. Run the pipeline
python main.py

# 6. Export the dynamic GEXF for Gephi
python export_gexf.py
```

Outputs land in `outputs/`.

### Environment

Copy `.env.example` to `.env` and set any overrides (all have defaults).

---

## Gephi quick-start

1. **File → Open** → `outputs/trilogy_dynamic.gexf`
2. **Layout**: ForceAtlas 2 — run ~30 s, then stop
3. **Appearance → Nodes → Colour → Partition** → `first_book` (colour by book)
4. **Appearance → Edges → Colour → Ranking** → `avg_sentiment` (red = −1 … green = +1)
5. **Timeline panel** (bottom) → Enable → press Play to watch the network evolve
6. Screen-record the canvas while Timeline plays

---

## Technical notes

**Character extraction** (`src/characters.py`) uses capitalized-token frequency scoring with a two-pass blocklist (places, collective nouns, pronouns, mythological names) and an alias map for OCR variants and accented names (`fère→fere`, `bragelonne→raoul`, `oliver→cromwell`, etc.). Role references (`the King`, `the Cardinal`) are resolved to their most co-occurring named character in each window.

**Scene detection** (`src/scenes.py`) uses a 2 000-character sliding window with a 1 000-character step. Scenes are validated for non-empty spans, in-bounds offsets, and presence of at least two known characters.

**Sentiment** is computed with VADER on the full scene text. Each edge's `avg_sentiment` is the mean compound score across all scenes where the pair co-appears in the window.

**Structural balance** (`src/analysis.py`) counts triangles whose three edge signs multiply to +1 (balanced: friends of friends are friends; enemies of enemies are friends) and divides by total triangle count.
