"""
Preprocessing only: clean + chapter-split all 6 books.
Does NOT call the LLM.  Run once to populate data/clean/ and data/chapters/.

Usage:
    python split_books.py
"""
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent))

from src.config import BOOKS, RAW_DIR, CLEAN_DIR, CHAPTERS_DIR
from src.preprocessing import load_raw, clean_text, save_clean, load_clean
from src.chapter_parser import split_into_chapters, save_chapters, load_chapters


def main() -> None:
    for book_key, filename in BOOKS.items():
        raw_path = RAW_DIR / filename
        if not raw_path.exists():
            print(f"[SKIP] {raw_path} not found")
            continue

        # --- Clean ---
        clean_path = CLEAN_DIR / f"{book_key}.txt"
        if clean_path.exists():
            print(f"[clean]  {book_key}: cached")
            text = load_clean(book_key)
        else:
            print(f"[clean]  {book_key}: processing …", end=" ", flush=True)
            raw  = load_raw(book_key, filename)
            text = clean_text(raw)
            save_clean(book_key, text)
            print(f"{len(text):,} chars")

        # --- Chapters ---
        chapters_path = CHAPTERS_DIR / f"{book_key}.json"
        if chapters_path.exists():
            chapters = load_chapters(book_key)
            print(f"[split]  {book_key}: cached  ({len(chapters)} chapters)")
        else:
            print(f"[split]  {book_key}: splitting …", end=" ", flush=True)
            chapters = split_into_chapters(text)
            save_chapters(book_key, chapters)
            print(f"{len(chapters)} chapters detected")

        # Print first few chapter headings for a sanity-check
        for ch in chapters[:3]:
            snippet = ch["text"][:80].replace("\n", " ")
            print(f"         ch.{ch['chapter']:>3}: {snippet}")
        print()


if __name__ == "__main__":
    main()
