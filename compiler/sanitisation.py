"""
Typst sanitisation utilities.

Cleans LLM-generated Typst markup: normalizes Unicode, collapses unusual
whitespace characters, and strips invisible/control characters that would
break compilation or corrupt the output.

Typst is Unicode-native, so unlike the old LaTeX sanitiser we deliberately
KEEP typographic characters (smart quotes, em dashes, Greek letters, arrows,
math operators) — the default fonts render them correctly.
"""

import logging
import re
import unicodedata

# Characters replaced with plain equivalents.
UNICODE_TYPST_MAP = {
    # --- Spaces ---
    "\u00A0": " ",            # non-breaking space
    "\u202F": " ",            # narrow no-break space
    "\u2007": " ",            # figure space
    "\u2009": " ",            # thin space
    "\u200A": " ",            # hair space
}

# Invisible / control characters removed outright.
_INVISIBLE_RE = re.compile(
    "[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F"
    "\u200B\u200C\u200D\u2060\uFEFF]"
)


def sanitize_typst(markup: str) -> str:
    """
    Sanitise LLM-generated Typst markup by normalizing Unicode, collapsing
    unusual whitespace, and stripping invisible/control characters.
    """
    # 1. Normalize unicode
    markup = unicodedata.normalize("NFKC", markup)

    # 2. Replace unusual whitespace characters
    for char, replacement in UNICODE_TYPST_MAP.items():
        markup = markup.replace(char, replacement)

    # 3. Remove invisible / control characters — but say what was dropped
    #    instead of deleting silently.
    dropped = set(_INVISIBLE_RE.findall(markup))
    if dropped:
        logging.getLogger("pipeline").warning(
            "sanitize_typst: dropping %d invisible/control character(s): %s",
            len(dropped), " ".join(sorted(dropped)),
        )
    markup = _INVISIBLE_RE.sub("", markup)

    return markup
