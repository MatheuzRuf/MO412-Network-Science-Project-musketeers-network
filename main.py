"""
Three Musketeers Trilogy — Signed Character-Interaction Graphs.

Slides a window of WINDOW_CHAPTERS chapters across each book with a step of
STEP_CHAPTERS (default 1). Each window produces one signed NetworkX graph,
giving arc-level density with chapter-level temporal resolution.

Usage
-----
    python main.py

Place raw book .txt files in data/raw/ before running.

Outputs
-------
    outputs/graphs/<book>_w<start>_<end>.graphml / .json
    outputs/metrics.csv

Cached intermediate data:
    data/llm_outputs/characters/<book>_w<start>_<end>.json
    data/llm_outputs/scenes/<book>_w<start>_<end>.json

Defaults
--------
    WINDOW_CHAPTERS = 10   (~150k chars, arc-level density)
    STEP_CHAPTERS   =  1   (1-chapter temporal precision)
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from src.config import (
    BOOKS,
    RAW_DIR, CLEAN_DIR, CHAPTERS_DIR,
    GRAPHS_DIR, METRICS_CSV,
)
from src.preprocessing  import load_raw, clean_text, save_clean
from src.chapter_parser import split_into_chapters, save_chapters, load_chapters
from src.characters     import extract_characters, get_character_names
from src.scenes         import extract_scenes
from src.graph_builder  import build_graph
from src.analysis       import compute_metrics, balance_ratio
from src.export         import save_graph, save_metrics

# ---------------------------------------------------------------------------
# Tunable parameters
# ---------------------------------------------------------------------------
WINDOW_CHAPTERS = 10   # number of chapters per window
STEP_CHAPTERS   = 1    # chapters advanced per step


def process_book(book_key: str, filename: str) -> list[dict]:
    """Slide a chapter window across one book. Returns per-window metric dicts."""
    logger.info("=" * 60)
    logger.info("Processing %s  (win=%d  step=%d)", book_key, WINDOW_CHAPTERS, STEP_CHAPTERS)
    logger.info("=" * 60)

    # 1. Load & clean (reuse cache)
    clean_path = CLEAN_DIR / f"{book_key}.txt"
    if clean_path.exists():
        text = clean_path.read_text(encoding="utf-8")
    else:
        raw  = load_raw(book_key, filename)
        text = clean_text(raw)
        save_clean(book_key, text)

    # 2. Load chapters (reuse cache)
    chapters_path = CHAPTERS_DIR / f"{book_key}.json"
    if chapters_path.exists():
        chapters = load_chapters(book_key)
    else:
        chapters = split_into_chapters(text)
        save_chapters(book_key, chapters)

    logger.info("Chapters: %d  →  %d windows", len(chapters),
                max(0, len(chapters) - WINDOW_CHAPTERS + 1))

    metrics_records: list[dict] = []

    # Sort chapters by number to guarantee order
    chapters_sorted = sorted(chapters, key=lambda c: c["chapter"])

    for i in range(0, len(chapters_sorted) - WINDOW_CHAPTERS + 1, STEP_CHAPTERS):
        window   = chapters_sorted[i : i + WINDOW_CHAPTERS]
        first_ch = window[0]["chapter"]
        last_ch  = window[-1]["chapter"]
        win_id   = f"{book_key}_w{first_ch:03d}_{last_ch:03d}"
        win_text = "\n\n".join(c["text"] for c in window)

        if len(win_text) < 1000:
            logger.debug("  [%s] too short — skipping", win_id)
            continue

        # Characters
        characters = extract_characters(win_id, win_text)
        char_names = get_character_names(characters)
        if len(char_names) < 2:
            logger.info("  [%s] <2 characters — skipping", win_id)
            continue

        # Scenes
        scenes = extract_scenes(win_id, win_text, characters)

        if not scenes:
            logger.info("  [%s] no valid scenes — skipping", win_id)
            continue

        # Graph
        G = build_graph(scenes, win_text)
        if G.number_of_edges() == 0:
            logger.info("  [%s] empty graph — skipping", win_id)
            continue

        save_graph(win_id, G)

        metrics = compute_metrics(G)
        balance = balance_ratio(G)
        record  = {
            "window":   win_id,
            "book":     book_key,
            "first_ch": first_ch,
            "last_ch":  last_ch,
            **metrics,
            "balance":  round(balance, 4),
        }
        metrics_records.append(record)
        logger.info(
            "  [%s] %d nodes, %d edges | sentiment=%.3f | balance=%.3f",
            win_id, metrics["nodes"], metrics["edges"],
            metrics["avg_sentiment"], balance,
        )

    logger.info("Book %s done: %d windows with graphs", book_key, len(metrics_records))
    return metrics_records


def main() -> None:
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    if METRICS_CSV.exists():
        METRICS_CSV.unlink()

    all_records: list[dict] = []

    for book_key, filename in BOOKS.items():
        raw_path = RAW_DIR / filename
        if not raw_path.exists():
            logger.warning("Raw file not found: %s — skipping %s", raw_path, book_key)
            continue
        records = process_book(book_key, filename)
        all_records.extend(records)
        save_metrics(records)

    logger.info("Done. %d windows generated across all books.", len(all_records))


if __name__ == "__main__":
    main()
