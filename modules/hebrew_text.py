"""Fix Hebrew text that PDF extractors return in *visual* order.

Many Israeli insurance PDFs store each line left-to-right as it is drawn, so
pdfplumber returns "חפסנ" instead of "נספח" (while numbers stay correct).
The AI then misses words like "פיזיותרפיה". We detect that case and run the
Unicode bidi algorithm on each line, which restores logical order and keeps
numbers, percentages and section numbers (4.9.1, 80%, 120 ₪) intact.
"""
import re

try:
    from bidi.algorithm import get_display
except Exception:  # python-bidi missing → leave text as is
    get_display = None

_FINALS = "ךםןףץ"
_HEB_WORD = re.compile(r"[א-ת]{2,}")


def reversed_hebrew_score(text: str) -> tuple[int, int]:
    """(words that START with a final letter, words that END with one).
    Logical Hebrew never starts a word with ך/ם/ן/ף/ץ; visual-order text does."""
    starts = ends = 0
    for w in _HEB_WORD.findall(text or ""):
        if w[0] in _FINALS:
            starts += 1
        if w[-1] in _FINALS:
            ends += 1
    return starts, ends


def looks_reversed(text: str, min_words: int = 5) -> bool:
    starts, ends = reversed_hebrew_score(text)
    return starts >= min_words and starts > 3 * ends


def to_logical(text: str) -> str:
    """Visual → logical, line by line (only call when looks_reversed)."""
    if get_display is None:
        return text
    return "\n".join(get_display(line, base_dir="R") if line.strip() else line
                     for line in text.split("\n"))


def fix_visual_hebrew(text: str, min_words: int = 5) -> str:
    """Return text in logical order if it was extracted in visual order; otherwise unchanged."""
    if text and looks_reversed(text, min_words):
        return to_logical(text)
    return text
