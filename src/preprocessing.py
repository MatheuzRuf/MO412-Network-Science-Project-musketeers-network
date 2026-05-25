"""
Load, clean, and persist raw book text.
"""
import re
import unicodedata

from src.config import RAW_DIR, CLEAN_DIR


def load_raw(book_key: str, filename: str) -> str:
    path = RAW_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _strip_gutenberg(text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_gutenberg(text: str) -> str:
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
    ]
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[idx + len(marker):]
            newline = text.find("\n")
            if newline != -1:
                text = text[newline + 1:]
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text


def save_clean(book_key: str, text: str) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    path = CLEAN_DIR / f"{book_key}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_clean(book_key: str) -> str:
    path = CLEAN_DIR / f"{book_key}.txt"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
