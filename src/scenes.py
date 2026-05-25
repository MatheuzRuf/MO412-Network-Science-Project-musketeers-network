"""
Heuristic scene detection via sliding-window co-occurrence — no API, no key.

Approach
--------
Slide a window of WINDOW_SIZE characters over the text with STEP overlap.
A window becomes a "scene" when two or more known characters are mentioned
within it. Characters are detected by searching for canonical names (and their
original-case aliases) in the lowercased window text.

This is a co-occurrence proxy for genuine interaction: it over-counts scenes
but captures the correct character pairs for network analysis.
"""
import json
import logging

from src.config import SCENES_DIR

logger = logging.getLogger(__name__)

# Window and step size in characters.
# ~2 000 chars ≈ 300-400 words, roughly one exchange / short scene.
WINDOW_SIZE = 2_000
STEP_SIZE   = 1_000   # 50 % overlap so cross-window interactions are captured


def _build_search_terms(characters: dict) -> list[tuple[str, list[str]]]:
    """Return list of (canonical_name, [surface_forms]) pairs."""
    terms = []
    for char in characters.get("characters", []):
        canonical = char["name"]
        forms = {canonical} | {a.lower() for a in char.get("aliases", [])}
        terms.append((canonical, list(forms)))
    return terms


def _chars_in_window(window_lower: str,
                     terms: list[tuple[str, list[str]]]) -> list[str]:
    """Return canonical names of characters found in the lowercased window."""
    found = []
    for canonical, forms in terms:
        for form in forms:
            if form in window_lower:
                found.append(canonical)
                break
    return found


def _validate(scenes: list[dict], text: str,
              valid_characters: list[str]) -> list[dict]:
    """
    Keep only scenes that satisfy all constraints and re-number sequentially.

    Constraints: start_char < end_char, end_char <= len(text),
    at least 2 characters, all characters in valid_characters.
    """
    valid_set = set(valid_characters)
    valid: list[dict] = []
    stats = {"empty_span": 0, "out_of_bounds": 0, "too_few_chars": 0, "unknown_chars": 0}

    for scene in scenes:
        start = scene.get("start_char", 0)
        end   = scene.get("end_char",   0)
        chars = scene.get("characters", [])

        if start >= end:
            stats["empty_span"] += 1
            continue
        if end > len(text):
            stats["out_of_bounds"] += 1
            continue
        if len(chars) < 2:
            stats["too_few_chars"] += 1
            continue
        unknown = [c for c in chars if c not in valid_set]
        if unknown:
            stats["unknown_chars"] += 1
            logger.debug("Unknown characters in scene: %s", unknown)
            continue

        valid.append(scene)

    for idx, scene in enumerate(valid):
        scene["scene_id"] = idx + 1

    rejected = sum(stats.values())
    logger.info("Validation: %d valid, %d rejected %s", len(valid), rejected, stats)
    return valid


def extract_scenes(win_id: str, text: str, characters: dict) -> list[dict]:
    """
    Detect and validate scenes via heuristic. Results are cached.

    Returns list of {scene_id, start_char, end_char, characters}.
    """
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = SCENES_DIR / f"{win_id}.json"

    if cache_path.exists():
        logger.info("[scenes] Cache hit: %s", win_id)
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f).get("scenes", [])

    logger.info("[scenes] Heuristic scene detection: %s", win_id)

    terms    = _build_search_terms(characters)
    char_names = [t[0] for t in terms]
    scenes: list[dict] = []
    scene_id = 1
    pos = 0
    n   = len(text)

    while pos < n:
        end     = min(pos + WINDOW_SIZE, n)
        window  = text[pos:end]
        present = _chars_in_window(window.lower(), terms)

        if len(present) >= 2:
            scenes.append({
                "scene_id":   scene_id,
                "start_char": pos,
                "end_char":   end,
                "characters": present,
            })
            scene_id += 1

        pos += STEP_SIZE

    scenes = _validate(scenes, text, char_names)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"scenes": scenes}, f, ensure_ascii=False, indent=2)

    logger.info("[scenes] %d scenes found for %s", len(scenes), win_id)
    return scenes
