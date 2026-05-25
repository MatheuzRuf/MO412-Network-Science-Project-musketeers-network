"""
Split cleaned book text into numbered chapters.
"""
import re
import json

from src.config import CHAPTERS_DIR

# Patterns tried in order; first one yielding >= 5 chapters wins.
_PATTERNS = [
    re.compile(r"^CHAPTER\s+[IVXLCDM\d]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Chapter\s+[IVXLCDM\d]+", re.MULTILINE),
    re.compile(r"^\s*[IVXLCDM]{2,}\.\s*$", re.MULTILINE),  # Roman numeral alone
    re.compile(r"^[IVXLCDM]{2,}\s*$", re.MULTILINE),
]


def split_into_chapters(text: str) -> list[dict]:
    """
    Returns a list of {"chapter": int, "text": str} dicts.
    Falls back to equal-size chunking if no pattern matches well.
    """
    for pattern in _PATTERNS:
        chapters = _split_by_pattern(text, pattern)
        if len(chapters) >= 5:
            return chapters
    return _split_equal(text, n_chunks=60)


def _split_by_pattern(text: str, pattern: re.Pattern) -> list[dict]:
    matches = list(pattern.finditer(text))
    if not matches:
        return []
    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapter_text = text[start:end].strip()
        if chapter_text:
            chapters.append({"chapter": i + 1, "text": chapter_text})
    return chapters


def _split_equal(text: str, n_chunks: int) -> list[dict]:
    size = max(1, len(text) // n_chunks)
    chunks = []
    for i in range(n_chunks):
        chunk = text[i * size: (i + 1) * size].strip()
        if chunk:
            chunks.append({"chapter": i + 1, "text": chunk})
    return chunks


def save_chapters(book_key: str, chapters: list[dict]) -> None:
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_DIR / f"{book_key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)


def load_chapters(book_key: str) -> list[dict]:
    path = CHAPTERS_DIR / f"{book_key}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
