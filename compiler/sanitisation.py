"""
LaTeX sanitisation utilities.

Replaces problematic Unicode characters with LaTeX-safe equivalents and
strips non-printable characters that would break pdflatex/xelatex.
"""

import re
import unicodedata

UNICODE_LATEX_MAP = {
    # --- Dashes and hyphens ---
    "\u2014": "---",          # em dash
    "\u2013": "--",           # en dash
    "\u2212": "-",            # minus sign
    "\u2011": "-",            # non-breaking hyphen
    "\u2010": "-",            # hyphen

    # --- Quotation marks ---
    "\u201c": "``",           # left double quotation mark
    "\u201d": "''",           # right double quotation mark
    "\u2018": "`",            # left single quotation mark
    "\u2019": "'",            # right single quotation mark
    "\u201a": ",",            # single low-9 quotation mark
    "\u201e": ",,",           # double low-9 quotation mark
    "\u00ab": "<<",           # left-pointing double angle quotation
    "\u00bb": ">>",           # right-pointing double angle quotation

    # --- Spaces ---
    "\u00A0": " ",            # non-breaking space
    "\u202F": " ",            # narrow no-break space
    "\u2009": " ",            # thin space
    "\u200B": "",             # zero-width space
    "\u200C": "",             # zero-width non-joiner
    "\u200D": "",             # zero-width joiner
    "\uFEFF": "",             # byte order mark

    # --- Ellipsis, bullets, misc punctuation ---
    "\u2026": r"\ldots{}",    # horizontal ellipsis
    "\u2022": r"\textbullet{}", # bullet
    "\u2032": "'",            # prime
    "\u2033": "''",           # double prime
    "\u2192": r"\ensuremath{\rightarrow}", # rightwards arrow
    "\u2190": r"\ensuremath{\leftarrow}",  # leftwards arrow
    "\u21d2": r"\ensuremath{\Rightarrow}", # rightwards double arrow
    "\u21d0": r"\ensuremath{\Leftarrow}",  # leftwards double arrow
    "\u2194": r"\ensuremath{\leftrightarrow}", # left right arrow

    # --- Math operators and relations ---
    "\u00b0": r"\ensuremath{^\circ}",  # degree sign
    "\u00b1": r"\ensuremath{\pm}",     # plus-minus
    "\u00d7": r"\ensuremath{\times}",  # multiplication
    "\u00f7": r"\ensuremath{\div}",    # division
    "\u2264": r"\ensuremath{\leq}",    # less-than or equal
    "\u2265": r"\ensuremath{\geq}",    # greater-than or equal
    "\u2248": r"\ensuremath{\approx}", # almost equal
    "\u2260": r"\ensuremath{\neq}",    # not equal
    "\u2261": r"\ensuremath{\equiv}",  # identical to
    "\u221e": r"\ensuremath{\infty}",  # infinity
    "\u2211": r"\ensuremath{\sum}",    # n-ary summation
    "\u220f": r"\ensuremath{\prod}",   # n-ary product
    "\u221a": r"\ensuremath{\sqrt{}}", # square root
    "\u2202": r"\ensuremath{\partial}",# partial differential
    "\u2207": r"\ensuremath{\nabla}",  # nabla
    "\u2208": r"\ensuremath{\in}",     # element of
    "\u2209": r"\ensuremath{\notin}",  # not an element of
    "\u2229": r"\ensuremath{\cap}",    # intersection
    "\u222a": r"\ensuremath{\cup}",    # union
    "\u2282": r"\ensuremath{\subset}", # subset of
    "\u2286": r"\ensuremath{\subseteq}", # subset of or equal
    "\u2205": r"\ensuremath{\emptyset}", # empty set
    "\u2227": r"\ensuremath{\wedge}",  # logical and
    "\u2228": r"\ensuremath{\vee}",    # logical or
    "\u00ac": r"\ensuremath{\neg}",    # not sign
    "\u2203": r"\ensuremath{\exists}", # there exists
    "\u2200": r"\ensuremath{\forall}", # for all
    "\u22c5": r"\ensuremath{\cdot}",   # dot operator

    # --- Greek letters (lowercase) ---
    "\u03b1": r"\ensuremath{\alpha}",
    "\u03b2": r"\ensuremath{\beta}",
    "\u03b3": r"\ensuremath{\gamma}",
    "\u03b4": r"\ensuremath{\delta}",
    "\u03b5": r"\ensuremath{\varepsilon}",
    "\u03b6": r"\ensuremath{\zeta}",
    "\u03b7": r"\ensuremath{\eta}",
    "\u03b8": r"\ensuremath{\theta}",
    "\u03b9": r"\ensuremath{\iota}",
    "\u03ba": r"\ensuremath{\kappa}",
    "\u03bb": r"\ensuremath{\lambda}",
    "\u03bc": r"\ensuremath{\mu}",
    "\u03bd": r"\ensuremath{\nu}",
    "\u03be": r"\ensuremath{\xi}",
    "\u03c0": r"\ensuremath{\pi}",
    "\u03c1": r"\ensuremath{\rho}",
    "\u03c3": r"\ensuremath{\sigma}",
    "\u03c4": r"\ensuremath{\tau}",
    "\u03c6": r"\ensuremath{\phi}",
    "\u03c7": r"\ensuremath{\chi}",
    "\u03c8": r"\ensuremath{\psi}",
    "\u03c9": r"\ensuremath{\omega}",

    # --- Greek letters (uppercase) ---
    "\u0393": r"\ensuremath{\Gamma}",
    "\u0394": r"\ensuremath{\Delta}",
    "\u0398": r"\ensuremath{\Theta}",
    "\u039b": r"\ensuremath{\Lambda}",
    "\u039e": r"\ensuremath{\Xi}",
    "\u03a0": r"\ensuremath{\Pi}",
    "\u03a3": r"\ensuremath{\Sigma}",
    "\u03a6": r"\ensuremath{\Phi}",
    "\u03a8": r"\ensuremath{\Psi}",
    "\u03a9": r"\ensuremath{\Omega}",

    # --- Superscripts and subscripts ---
    "\u00b2": r"\ensuremath{^2}",  # superscript 2
    "\u00b3": r"\ensuremath{^3}",  # superscript 3
    "\u2070": r"\ensuremath{^0}",  # superscript 0
    "\u00b9": r"\ensuremath{^1}",  # superscript 1
    "\u2074": r"\ensuremath{^4}",  # superscript 4
    "\u2080": r"\ensuremath{_0}",  # subscript 0
    "\u2081": r"\ensuremath{_1}",  # subscript 1
    "\u2082": r"\ensuremath{_2}",  # subscript 2
    "\u2083": r"\ensuremath{_3}",  # subscript 3

    # --- Misc symbols ---
    "\u2020": r"\ensuremath{\dagger}",   # dagger
    "\u2021": r"\ensuremath{\ddagger}",  # double dagger
    "\u00a9": r"\copyright",              # copyright
    "\u00ae": r"\textregistered",          # registered
    "\u2122": r"\texttrademark",  # trademark
}


def sanitize_latex(latex_code: str) -> str:
    """
    Sanitise LLM-generated LaTeX by replacing problematic Unicode
    characters with LaTeX-safe equivalents.
    """
    # 1. Normalize unicode
    latex_code = unicodedata.normalize("NFKC", latex_code)

    # 2. Replace known problematic characters
    for char, replacement in UNICODE_LATEX_MAP.items():
        latex_code = latex_code.replace(char, replacement)

    # 3. Remove remaining non-ASCII characters that slipped through
    latex_code = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", latex_code)

    return latex_code
