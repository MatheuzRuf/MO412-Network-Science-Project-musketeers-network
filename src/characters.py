"""
Heuristic character extraction — no API, no key, no extra packages.

Strategy
--------
1. Titled names  : "M. Athos", "Monsieur d'Artagnan", "Cardinal Richelieu" …
2. Speech attribution : "said Porthos", "replied Aramis" …
3. Inline proper nouns : capitalized tokens that appear inside a sentence
   (not at the start of a sentence/paragraph, where any word is capitalised).

Each pattern adds a weight; names whose total weight exceeds a threshold
are kept as characters.
"""
import json
import logging
import re
from collections import Counter

from src.config import CHARACTERS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_TITLE_PFX = (
    r"M\.|Mme\.|Mlle\.|MM\."
    r"|Monsieur|Madame|Mademoiselle"
    r"|Milady|Milord|Lord|Lady|Sir"
    r"|Captain|Colonel|General|Lieutenant"
    r"|Count|Comte|Countess|Comtesse"
    r"|Duke|Duc|Duchess|Baron|Baroness"
    r"|Prince|Princess|King|Queen"
    r"|Bishop|Cardinal|Father|Reverend|Abbe|Abbé"
    r"|Doctor|Chevalier|Vicomte|Viscount"
)
# Titled name: title + optional whitespace + capitalised word(s)
_TITLED_RE = re.compile(
    rf"(?:{_TITLE_PFX})\s+([A-Z][A-Za-záàâäéèêëíìîïóòôöúùûüç'\-]{{2,}}"
    rf"(?:\s+[A-Z][A-Za-záàâäéèêëíìîïóòôöúùûüç'\-]{{2,}})?)",
    re.UNICODE,
)

# Speech attribution: verb + capitalised name directly after
_SPEECH_RE = re.compile(
    r"\b(?:said|says|replied|asked|cried|exclaimed|answered|murmured"
    r"|whispered|shouted|continued|added|returned|observed|remarked"
    r"|interrupted|demanded|urged|entreated|faltered|rejoined|resumed)"
    r"\s+([A-Z][A-Za-záàâäéèêëíìîïóòôöúùûüç'\-]{2,})",
    re.UNICODE,
)

# Inline proper noun: a capitalised token that is NOT sentence-initial
# (preceded by a lowercase char, comma, semicolon, colon, or closing quote)
_INLINE_RE = re.compile(
    r"(?<=[a-záàâäéèêëíìîïóòôöúùûüç,;:!?'\"\u201d])\s+"
    r"([A-Z][A-Za-záàâäéèêëíìîïóòôöúùûüç'\-]{2,})",
    re.UNICODE,
)

# Strip em-dash suffixes (e.g. "Aramis--" or "Fouquet--whom") and trailing
# punctuation produced by old-text typesetting conventions.
_EMDASH_RE = re.compile(r"--.*$")


def _clean_name(name: str) -> str:
    name = _EMDASH_RE.sub("", name)
    return name.rstrip(" -,;.!?'\"")

# Words that are capitalised for reasons other than being names
_STOPWORDS = {
    # Conjunctions / connectives
    "The", "This", "That", "These", "Those",
    "When", "While", "After", "Before", "Although", "Because",
    "However", "Therefore", "Indeed", "Perhaps", "Moreover",
    "Nevertheless", "Consequently", "Meanwhile", "Suddenly",
    "But", "And", "For", "Nor", "Yet", "So",
    # Countries / major cities already in text as proper nouns
    "France", "Paris", "England", "London", "Spain", "Rome",
    "Austria", "Flanders", "Holland", "Germany", "Italy",
    "Versailles", "Fontainebleau", "Vincennes",
    # Places specific to the Three Musketeers trilogy
    "Bastille", "Louvre", "Luxembourg", "Fossoyeurs",
    "Vaugirard", "Meung", "Béarn", "Gascony",
    "Hôtel", "Rue", "Palais", "Château",
    # Nationality / group nouns
    "French", "English", "Spanish", "Italian", "Gascon", "Gascons",
    "Huguenots", "Guards", "Guardsman", "Guardsmen",
    "Musketeer", "Musketeers",
    # Generic role / title words used anaphorically (without a name)
    "King", "Queen", "Cardinal", "Duke", "Duc", "Duchess",
    "Lord", "Lady", "Count", "Countess", "Comte", "Comtesse",
    "Prince", "Princess", "Baron", "Baroness",
    "Captain", "Colonel", "General", "Lieutenant", "Governor",
    "Monsieur", "Madame", "Mademoiselle",
    "Master", "Doctor", "Bishop", "Father", "Abbe", "Abbé",
    "Vicomte", "Chevalier", "Viscount",
    # Honorifics / forms of address
    "God", "Heaven", "Hell", "Majesty", "Highness", "Excellency",
    "Eminence", "Holiness", "Grace",
    # Structural
    "Chapter", "Book", "Part", "Volume",
    # Common English words that appear capitalised mid-sentence in old translations
    "Come", "Let", "What", "You", "Ah", "Oh",
    "Red", "Cross", "Don", "Jolly", "Miller",
    # Pronouns / determiners
    "Her", "His", "She", "They", "Then", "There", "All",
    # Additional places — British
    "Newcastle", "Scotland", "Norfolk", "Worcester", "Sheffield",
    "Whitehall", "Greenwich", "Hampton", "Portsmouth", "Spithead",
    "Tweed", "Tyne", "Ireland", "Britain",
    # Additional places — French / European
    "Africa", "Amiens", "Angers", "Anjou", "Antibes", "Armentières",
    "Beauvais", "Blois", "Boulogne", "Bretagne", "Brussels", "Burgundy",
    "Calais", "Cambrin", "Chaillot", "Charenton", "Compiègne", "Croisic",
    "Dover", "Etampes", "Europe", "Havre", "Hague", "Joigny",
    "Lens", "Lille", "Loire", "Lyon", "Melun", "Montdidier", "Nantes",
    "Neufchâtel", "Normandy", "Noyon", "Paimboeuf", "Rochelle",
    "Rueil", "Sarzeau", "Scheveningen", "Toulon", "Tours",
    # Common nouns / titles mistaken for names
    "Art", "Bridge", "Church", "Court", "Fort", "Ghost", "Golden",
    "Gospel", "Grand", "Great", "Holy", "Isle", "Just", "Marshal",
    "Mass", "Notre", "Officer", "Place", "Royal", "Saint", "Spring",
    "States", "Well",
    # French common words
    "Dieu", "Père", "Reine", "Roi", "Seigneur",
    # Mythological / classical
    "Diana", "Mars", "Venus", "Vulcan", "Cerberus", "Morpheus",
    "Virgil", "Macbeth",
    # Collective nationality / group nouns
    "Swiss", "Dutch", "Frenchman", "Englishman", "Frenchmen", "Englishmen",
    "Puritan", "Puritans", "Jesuit", "Jesuits", "Franciscan",
    "Carmelites", "Breton", "Bretons", "Scotch", "Scots", "Scottish",
    "Scotchman", "Frondeurs", "Minimes", "Highlanders", "Frondist",
    "Indian", "Indians", "Arabs", "Mazarinists", "Mazarinist",
    "Epicureans", "Parisians", "Rochellais", "Spaniard", "Spaniards",
    "Frondeur", "Frondists",
    # More places (cities, estates, streets, fortresses)
    "Bastile", "Vannes", "Belle-Isle", "Pierrefonds", "Vaux",
    "Chantilly", "Tyburn", "Noisy", "Bruges", "Harpe", "Lombards",
    "Cours", "Villars-Cotterets", "Mazingarbe",
    # More common nouns / noise
    "Hotel", "Pont", "Ville", "Why", "Latin", "Mme", "The",
    "Monseigneur", "Miss", "Maréchal", "Marechal",
    "Fronde", "Backson", "Gardes", "Pointe", "Dovecot",
    "Garter", "Pentecost", "Messalina", "Castle", "United", "Provinces",
    # More collective / group nouns missed previously
    "Venetian", "Venetians", "Catholic", "Catholics", "Huguenot",
    "Parisian", "Dominicans", "Englishwoman", "Beguine", "Beguines",
    # More places and noise
    "Palais-Cardinal", "Image-De-Notre-Dame", "Coldstream", "Rond-Point",
    "Herbes", "Voliere", "Chancellor", "Infanta",
    "Demon", "Fortune", "Lys",
    # French common nouns
    "Ours", "Neuf", "Parpaillot",
}

# Lowercase blocklist: names that pass scoring but are not real characters.
# Checked after lowercasing, as a second-pass filter.
_NAME_BLOCKLIST = {
    # Places
    "bastille", "louvre", "luxembourg", "fossoyeurs", "vaugirard",
    "vieux-colombier", "meung", "hôtel", "rue", "béarn", "gascony",
    "austria", "versailles", "fontainebleau", "vincennes", "palais",
    "château", "flanders", "holland",
    # Generic roles (lowercase)
    "king", "queen", "cardinal", "duke", "duc", "duchess",
    "lord", "lady", "count", "countess", "comte", "comtesse",
    "prince", "princess", "baron", "baroness",
    "captain", "colonel", "general", "lieutenant", "governor",
    "monsieur", "madame", "mademoiselle",
    "master", "doctor", "bishop", "father", "abbe", "abbé",
    "vicomte", "chevalier", "viscount",
    # Groups
    "gascon", "gascons", "huguenots", "guards", "guardsman", "guardsmen",
    "musketeer", "musketeers", "soldiers", "gentlemen",
    # Honorifics
    "majesty", "highness", "excellency", "eminence", "holiness", "grace",
    # Garbage / noise
    "hypocrite", "so-and-so", "man-in-a-hurry", "what", "you", "let",
    "come", "cross", "red", "don", "miller", "quixote", "solomon",
    "xiii", "xiv", "jolly", "ah", "oh",
    # Pronouns and determiners
    "her", "his", "she", "they", "then", "there", "all",
    # Additional place names — British
    "britain", "scotland", "ireland", "newcastle", "norfolk", "worcester",
    "sheffield", "whitehall", "greenwich", "hampton", "portsmouth",
    "spithead", "tweed", "tyne",
    # Additional place names — French / European
    "africa", "amiens", "angers", "anjou", "antibes", "armentières",
    "beauvais", "blois", "boulogne", "bretagne", "brussels", "burgundy",
    "calais", "cambrin", "chaillot", "charenton", "compiègne", "croisic",
    "dover", "etampes", "europe", "hague", "havre", "joigny",
    "lens", "lille", "loire", "lyon", "melun", "montdidier", "nantes",
    "neufchâtel", "normandy", "noyon", "paimboeuf", "rochelle",
    "roche-bernard", "rueil", "saint-germain", "saint-louis", "saint-mande",
    "saint-patern", "sainte-marguerite", "sarzeau", "scheveningen",
    "toulon", "tours",
    # Common nouns / exclamations mistaken for names
    "acquires", "are", "art", "beau", "bridge", "church", "commissary",
    "constable", "court", "coxcomb", "dame", "does", "dogs",
    "equinox", "fleece", "fort", "ghost", "golden", "gospel",
    "grand", "great", "greatness", "greek", "have", "here", "holy",
    "how", "isle", "jester", "just", "justice", "majesties",
    "marshal", "mass", "mordioux", "number", "officer", "one",
    "paradise", "place", "preacher", "principal", "providence",
    "royal", "royale", "saint", "seigneur", "speak", "spring",
    "states", "was", "wednesday", "well", "with", "yes",
    # French common words
    "deum", "dieu", "monarque", "notre", "père", "quai", "reine", "roi",
    # Mythological / classical references (poetry and play quotations)
    "amaryllis", "amyntas", "aquilo", "ariste", "candaules", "cerberus",
    "danae", "diana", "dryad", "dryads", "epicurus", "galatea",
    "macbeth", "macerinus", "mars", "morpheus", "naiad", "phyllis",
    "tyrcis", "venus", "virgil", "vulcan",
    # Collective nationality / group nouns
    "swiss", "dutch", "frenchman", "englishman", "frenchmen", "englishmen",
    "puritan", "puritans", "jesuit", "jesuits", "franciscan",
    "carmelites", "breton", "bretons", "scotch", "scots", "scottish",
    "scotchman", "frondeurs", "minimes", "highlanders", "frondist",
    "indian", "indians", "arabs", "mazarinists", "mazarinist",
    "epicureans", "parisians", "rochellais", "spaniard", "spaniards",
    "frondeur", "frondists",
    # More places (cities, estates, streets, fortresses)
    "bastile", "vannes", "belle-isle", "pierrefonds", "vaux",
    "greve", "grève", "chantilly", "tyburn", "noisy", "bruges",
    "cours", "harpe", "lombards", "wells", "pont",
    "villars-cotterets", "mazingarbe",
    # More common nouns / noise
    "hotel", "ville", "why", "latin", "mme", "the", "iii",
    "monseigneur", "miss", "maréchal", "marechal", "fronde",
    "backson", "gardes", "pointe", "dovecot", "garter", "pentecost",
    "messalina", "castle", "united", "provinces",
    # More collective / group nouns missed previously
    "venetian", "venetians", "catholic", "catholics", "huguenot",
    "parisian", "dominicans", "englishwoman", "beguine", "beguines",
    # More places and noise
    "palais-cardinal", "image-de-notre-dame", "coldstream", "rond-point",
    "herbes", "voliere", "chancellor", "infanta",
    "demon", "fortune", "lys", "i",
    # French common nouns
    "ours", "neuf", "parpaillot",
}


# ---------------------------------------------------------------------------
# Character alias / normalization map
# ---------------------------------------------------------------------------
# Maps lowercase variant spellings to the canonical lowercase name.
# Applied after extraction to merge nodes split by accent/OCR differences.
_CHAR_ALIASES: dict[str, str] = {
    "fère":            "athos",      # Comte de La Fère = Athos
    "fere":            "athos",      # unaccented form also = Athos
    "condé":           "conde",      # Prince de Condé
    "henriette":       "henrietta",  # Henrietta of England
    "danicamp":        "manicamp",   # OCR error variant
    "bonancieux":      "bonacieux",  # spelling variant
    "béthune":         "bethune",    # variant spelling
    # New merges
    "bragelonne":      "raoul",      # Raoul, Vicomte de Bragelonne (same person)
    "mazarini":        "mazarin",    # Italian form of his name
    "chatillon":       "châtillon",  # unaccented variant
    "louis xiv":       "louis",      # explicit style → canonical node
    "oliver cromwell": "cromwell",   # full name → canonical node
    "oliver":          "cromwell",   # short form also refers to Cromwell
    "henrietta stuart": "henrietta", # full name → canonical node
    "orléans":         "orleans",    # accent variant
    "gramont":         "grammont",   # spelling variant
}

# ---------------------------------------------------------------------------
# Role-reference resolution
# ---------------------------------------------------------------------------
# Standalone title/role patterns (e.g. "the Cardinal said", "replied Milady").
# For each, we attempt to identify the named character they refer to by
# measuring co-occurrence within a local context window. If one character
# dominates (≥ _RESOLVE_DOMINANCE of occurrences), the role is added as an
# alias of that character so scenes that mention only the title still register
# the correct node. Otherwise the role becomes its own anonymous character.
_ROLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bMilady\b"),                     "milady"),
    (re.compile(r"\bMilord\b"),                     "milord"),
    (re.compile(r"\bthe\s+Cardinal\b",  re.IGNORECASE), "cardinal"),
    (re.compile(r"\bthe\s+King\b",      re.IGNORECASE), "king"),
    (re.compile(r"\bthe\s+Queen\b",     re.IGNORECASE), "queen"),
    (re.compile(r"\bthe\s+Bishop\b",    re.IGNORECASE), "bishop"),
    (re.compile(r"\bthe\s+Vicomte\b",   re.IGNORECASE), "vicomte"),
    (re.compile(r"\bthe\s+Governor\b",  re.IGNORECASE), "governor"),
    (re.compile(r"\bthe\s+Infanta\b",   re.IGNORECASE), "infanta"),
]

_RESOLVE_CONTEXT   = 400   # chars on each side of a role mention
_RESOLVE_MIN_HITS  = 3     # roles appearing fewer times are skipped
_RESOLVE_DOMINANCE = 0.40  # fraction of contexts that must contain the winner

# Priority resolution: for known role→character mappings, use a relaxed
# threshold so these roles are resolved even in busy windows.
_RESOLVE_PRIORITY_DOMINANCE = 0.15
_ROLE_PRIORITY: dict[str, list[str]] = {
    "king":     ["louis", "louis xiii", "charles"],
    "queen":    ["anne", "henrietta", "theresa", "marie"],
    "cardinal": ["mazarin", "richelieu"],
    "vicomte":  ["raoul", "bragelonne"],
    "governor": ["baisemeaux", "saint-mars"],
    "milord":   ["buckingham", "winter"],
    "infanta":  ["theresa", "marie"],
}


def _resolve_roles(text: str, characters: list[dict]) -> list[dict]:
    """
    Scan for role/title mentions and resolve each to a named character or
    keep as a standalone node.

    For each role pattern, every occurrence is examined in a ±_RESOLVE_CONTEXT
    char window. If one named character appears in ≥ _RESOLVE_DOMINANCE of
    those windows it is the likely referent: the role surface form is added as
    an alias so scene detection captures it automatically. If no dominant match
    is found the role becomes its own character node.

    Modifies `characters` in-place (alias injection). Returns new standalone
    role-node dicts to be appended.
    """
    existing = {c["name"]: c for c in characters}
    additions: list[dict] = []

    for pattern, role_name in _ROLE_PATTERNS:
        if role_name in existing:
            continue   # already extracted by primary heuristic

        positions = [m.start() for m in pattern.finditer(text)]
        if len(positions) < _RESOLVE_MIN_HITS:
            continue

        cooccur: Counter = Counter()
        for pos in positions:
            lo = max(0, pos - _RESOLVE_CONTEXT)
            hi = min(len(text), pos + _RESOLVE_CONTEXT)
            snippet = text[lo:hi].lower()
            for name in existing:
                if name in snippet:
                    cooccur[name] += 1

        alias = role_name.capitalize()   # e.g. "Cardinal", "King", "Milady"

        # Try known priority targets: pick the highest co-occurring candidate
        # present in this window, with no minimum threshold. Falls back to
        # list order when all co-occurrences are zero.
        resolved = False
        if role_name in _ROLE_PRIORITY:
            present = [t for t in _ROLE_PRIORITY[role_name] if t in existing]
            if present:
                best_target = max(present, key=lambda t: cooccur.get(t, 0))
                char = existing[best_target]
                if alias not in char.get("aliases", []):
                    char.setdefault("aliases", []).append(alias)
                ratio = cooccur.get(best_target, 0) / len(positions)
                logger.debug(
                    "[roles] %s → %s via priority (%.0f%%)",
                    role_name, best_target, ratio * 100,
                )
                resolved = True
        if resolved:
            continue

        # Fall back to open dominance search
        if cooccur:
            dominant, hits = cooccur.most_common(1)[0]
            ratio = hits / len(positions)
            if ratio >= _RESOLVE_DOMINANCE:
                char = existing[dominant]
                if alias not in char.get("aliases", []):
                    char.setdefault("aliases", []).append(alias)
                logger.debug(
                    "[roles] %s → %s (%.0f%% of contexts)",
                    role_name, dominant, ratio * 100,
                )
                continue

        # No dominant match — keep as a standalone role node
        logger.debug("[roles] %s → standalone node", role_name)
        additions.append({"name": role_name, "aliases": [alias]})

    return additions


def _score_candidates(text: str) -> Counter:
    counts: Counter = Counter()
    for m in _TITLED_RE.finditer(text):
        name = _clean_name(m.group(1).strip())
        if name and name not in _STOPWORDS:
            counts[name] += 3          # high confidence
    for m in _SPEECH_RE.finditer(text):
        name = _clean_name(m.group(1).strip())
        if name and name not in _STOPWORDS:
            counts[name] += 2          # medium confidence
    for m in _INLINE_RE.finditer(text):
        name = _clean_name(m.group(1).strip())
        if name and name not in _STOPWORDS:
            counts[name] += 1          # low confidence
    return counts


def extract_characters(win_id: str, text: str) -> dict:
    """
    Extract characters via heuristic. Results are cached.

    Returns {"characters": [{"name": str (lowercase), "aliases": [str]}, ...]}
    """
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CHARACTERS_DIR / f"{win_id}.json"

    if cache_path.exists():
        logger.info("[characters] Cache hit: %s", win_id)
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.info("[characters] Heuristic extraction: %s", win_id)

    counts = _score_candidates(text)

    # Minimum weighted score to be considered a real character
    MIN_SCORE = 4
    characters = [
        {"name": name.lower(), "aliases": [name]}
        for name, score in counts.most_common()
        if score >= MIN_SCORE and name.lower() not in _NAME_BLOCKLIST
    ]

    # Merge spelling/accent variants into canonical names
    merged: dict[str, dict] = {}
    for char in characters:
        canon: str = _CHAR_ALIASES.get(char["name"]) or char["name"]
        if canon in merged:
            for a in char.get("aliases", []):
                if a not in merged[canon]["aliases"]:
                    merged[canon]["aliases"].append(a)
        else:
            char = dict(char)
            char["name"] = canon
            merged[canon] = char
    characters = list(merged.values())

    # Resolve role/honorific references to named characters or standalone nodes
    role_additions = _resolve_roles(text, characters)
    characters.extend(role_additions)

    result = {"characters": characters}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("[characters] %d characters found for %s", len(characters), win_id)
    return result


def get_character_names(characters: dict) -> list[str]:
    """Return sorted list of canonical character names."""
    return sorted(c["name"] for c in characters.get("characters", []))
