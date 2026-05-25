"""
Central configuration: paths and book registry.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent

DATA_DIR        = BASE_DIR / "data"
RAW_DIR         = DATA_DIR / "raw"
CLEAN_DIR       = DATA_DIR / "clean"
CHAPTERS_DIR   = DATA_DIR / "chapters"
CACHE_DIR      = DATA_DIR / "cache"
CHARACTERS_DIR = CACHE_DIR / "characters"
SCENES_DIR     = CACHE_DIR / "scenes"

OUTPUTS_DIR = BASE_DIR / "outputs"
GRAPHS_DIR  = OUTPUTS_DIR / "graphs"
METRICS_CSV = OUTPUTS_DIR / "metrics.csv"

# ---------------------------------------------------------------------------
# Books
# The Vicomte de Bragelonne trilogy is split across four Gutenberg files
# (books 3–6); each restarts chapter numbering from I/1 internally.
# ---------------------------------------------------------------------------
BOOKS = {
    "book_1": "book1_theThreeMusketeers.txt",
    "book_2": "book2_twentyYearsLater.txt",
    "book_3": "book3_theVicomteDeBragelonne.txt",
    "book_4": "book4_tenYearsLater.txt",
    "book_5": "book5_louiseDeLaValliere.txt",
    "book_6": "book6_theManInTheIronMask.txt",
}
