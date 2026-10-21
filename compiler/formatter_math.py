"""
Deterministic Typst formatting utilities.

Handles markdown artifact stripping, LaTeX->Typst math conversion, notation
table generation, section compilation, and full document assembly.
No LLM calls — pure Python.
"""

import re
import unicodedata
from typing import Optional

from compiler.sanitisation import sanitize_typst


# ---------------------------------------------------------------------------
# LaTeX -> Typst math conversion
#
# LLMs keep producing LaTeX math despite the prompt, so every $...$ segment
# is converted deterministically. Anything still looking like regex/LaTeX
# afterwards (leftover backslashes, baseless carets, regex character classes)
# degrades to a #raw() literal instead of failing the compile.
# ---------------------------------------------------------------------------

_LATEX_COMMANDS = {
    # operators / relations
    "cdot": "dot", "times": "times", "div": "/", "pm": "plus.minus",
    "mp": "minus.plus", "ast": "ast", "star": "star",
    "leq": "<=", "le": "<=", "geq": ">=", "ge": ">=",
    "neq": "!=", "ne": "!=", "approx": "approx", "equiv": "equiv",
    "sim": "tilde", "simeq": "tilde.eq", "propto": "prop",
    "ll": "<<", "gg": ">>", "subset": "subset", "subseteq": "subset.eq",
    "supset": "supset", "supseteq": "supset.eq", "in": "in", "notin": "notin",
    "cup": "union", "cap": "intersect", "setminus": "setminus", "minus": "-",
    "emptyset": "nothing", "varnothing": "nothing",
    "land": "and", "wedge": "and", "lor": "or", "vee": "or", "neg": "not",
    "forall": "forall", "exists": "exists", "nexists": "not.exists",
    "mid": "divides", "parallel": "parallel",
    "to": "->", "rightarrow": "->", "leftarrow": "<-",
    "longrightarrow": "-->", "longleftarrow": "<--",
    "Rightarrow": "=>", "Leftarrow": "<=", "Leftrightarrow": "<=>",
    "leftrightarrow": "<->", "mapsto": "|->", "uparrow": "up.arrow",
    "downarrow": "down.arrow",
    # big operators / calculus
    "sum": "sum", "prod": "product", "int": "integral", "iint": "integral.double",
    "partial": "diff", "nabla": "nabla", "infty": "infinity",
    "oint": "integral.contour",
    # functions (render as plain words in Typst)
    "log": "log", "ln": "ln", "exp": "exp", "sin": "sin", "cos": "cos",
    "tan": "tan", "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "min": "min", "max": "max", "arg": "arg", "det": "det", "dim": "dim",
    "gcd": "gcd", "sup": "sup", "inf": "inf", "lim": "lim", "limsup": "limsup",
    "liminf": "liminf", "Pr": "Pr",
    # dots
    "ldots": "...", "dots": "...", "cdots": "dots.c", "vdots": "dots.v",
    "ddots": "dots.down", "dotso": "...",
    # delimiters
    "langle": "angle.l", "rangle": "angle.r",
    "lfloor": "floor.l", "rfloor": "floor.r",
    "lceil": "ceil.l", "rceil": "ceil.r",
    "lbrace": "{", "rbrace": "}",
    "vert": "|", "lvert": "|", "rvert": "|",
    "backslash": "\\", "%": "%", "&": "&",
    # spacing
    "quad": " ", "qquad": " ", "thinspace": " ", "negthinspace": "",
    # greek lowercase
    "alpha": "alpha", "beta": "beta", "gamma": "gamma", "delta": "delta",
    "epsilon": "epsilon", "varepsilon": "epsilon.alt", "zeta": "zeta",
    "eta": "eta", "theta": "theta", "vartheta": "theta.alt", "iota": "iota",
    "kappa": "kappa", "lambda": "lambda", "mu": "mu", "nu": "nu", "xi": "xi",
    "pi": "pi", "varpi": "pi.alt", "rho": "rho", "varrho": "rho.alt",
    "sigma": "sigma", "varsigma": "sigma.alt", "tau": "tau", "upsilon": "upsilon",
    "phi": "phi", "varphi": "phi.alt", "chi": "chi", "psi": "psi", "omega": "omega",
    # greek uppercase
    "Gamma": "Gamma", "Delta": "Delta", "Theta": "Theta", "Lambda": "Lambda",
    "Xi": "Xi", "Pi": "Pi", "Sigma": "Sigma", "Upsilon": "Upsilon",
    "Phi": "Phi", "Psi": "Psi", "Omega": "Omega",
    # accents
    "hat": "hat", "bar": "macron", "vec": "arrow", "tilde": "tilde",
    "dot": "dot.op", "ddot": "dot.op.double",
}

# Multi-letter names that exist in Typst math and must be left untouched.
# Anything else multi-letter gets quoted (Typst renders "word" as upright
# text), because unknown identifiers are hard compile errors.
_TYPST_MATH_KNOWN = set(
    """
    sqrt root pow frac abs norm floor ceil round trunc exp log ln sin cos tan
    sec csc cot arcsin arccos arctan sinh cosh tanh min max arg det dim gcd
    lcm inf sup lim liminf limsup Pr mod sum product integral cases vec mat
    augment overline underline strike upright italic bold serif sans mono frak
    cal bb accent hat tilde macron acute caron breve circle arrow op alt
    double triple contour stroked filled l r c v u d h big
    dot times div divides ast star plus minus eq lt gt le ge approx equiv
    tilde tilt prop subset supset union intersect setminus nothing in and or
    not forall exists mid parallel dagger ddagger bullet infinity
    arrow to gets lrm alpha beta gamma delta epsilon zeta eta theta iota
    kappa lambda mu nu xi pi rho sigma tau upsilon phi chi psi omega
    Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
    upright
    """.split()
)

_BRACED_FNS = [
    ("text", "upright"), ("mathrm", "upright"), ("operatorname", "upright"),
    ("mathit", "italic"), ("mathbf", "bold"), ("bm", "bold"),
    ("boldsymbol", "bold"), ("mathbb", "bb"), ("mathcal", "cal"),
    ("mathfrak", "frak"),
]


def _decompose_super_sub(s: str) -> str:
    """Turn Unicode super/subscript letters (Kᵀ, x², a₀) into Typst ^()/_()
    groups, merging runs. Must run before NFKC flattening destroys them."""
    out = []
    i = 0
    while i < len(s):
        d = unicodedata.decomposition(s[i])
        if d.startswith('<super>') or d.startswith('<sub>'):
            kind = '^' if d.startswith('<super>') else '_'
            base = unicodedata.normalize('NFKC', s[i])
            j = i + 1
            while j < len(s):
                dj = unicodedata.decomposition(s[j])
                kj = '^' if dj.startswith('<super>') else (
                    '_' if dj.startswith('<sub>') else '')
                if kj != kind:
                    break
                base += unicodedata.normalize('NFKC', s[j])
                j += 1
            out.append(f'{kind}({base})')
            i = j
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def convert_math_segment(seg: str) -> str:
    """Convert the inside of one $...$ math segment from LaTeX to Typst."""
    s = _decompose_super_sub(seg)
    # LLMs often double the backslash: \\alpha means \alpha.
    s = re.sub(r'\\\\([a-zA-Z]+)', r'\\\1', s)

    for _ in range(10):  # loop so nested braces resolve inner-first
        prev = s
        s = re.sub(r'\\(?:begin|end)\s*\{[^{}]*\}', '', s)
        for cmd, fn in _BRACED_FNS:
            s = re.sub(r'\\' + cmd + r'\s*\{([^{}]*)\}', fn + r'(\1)', s)
        s = re.sub(r'\\sqrt\s*\[([^\[\]]*)\]\s*\{([^{}]*)\}', r'root(\1, \2)', s)
        s = re.sub(r'\\sqrt\s*\{([^{}]*)\}', r'sqrt(\1)', s)
        s = re.sub(r'\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', r'(\1)/(\2)', s)
        s = re.sub(r'_\{([^{}]*)\}', r'_(\1)', s)
        s = re.sub(r'\^\{([^{}]*)\}', r'^(\1)', s)
        if s == prev:
            break

    # delimiter sizing prefixes
    s = re.sub(r'\\(?:left|right|[Bb]ig{1,2}[lr]?)\.?\s*', '', s)
    # thin/thick spaces, escaped braces
    s = re.sub(r'\\[,;:!]', ' ', s)
    s = s.replace(r'\{', '{').replace(r'\}', '}')
    # command words
    s = re.sub(
        r'\\([a-zA-Z]+)',
        lambda m: _LATEX_COMMANDS.get(m.group(1), m.group(0)),
        s,
    )
    # pair |...| into norm(...) so ambiguous pipe runs still compile
    s = re.sub(r'\|([^|\n]+?)\|', r'norm(\1)', s)
    # a slash needs operands for Typst's fraction syntax; a standalone or
    # space-delimited slash means the division operator
    if s.strip() == '/':
        return 'div'
    s = re.sub(r'(?<=\s)/(?=\s)', 'div', s)
    # LaTeX row separators and alignment characters have no Typst equivalent
    # here; drop them rather than break the equation.
    s = s.replace('\\\\', ' ')
    s = s.replace('&=', '=').replace('&', ' ')
    # bare brackets/braces start content blocks or group inside math; escape
    s = s.replace('[', '\\[').replace(']', '\\]')
    s = s.replace('{', '\\{').replace('}', '\\}')

    # Quote unknown multi-letter identifiers, skipping quoted regions
    # (Typst renders "word" upright); unknown bare identifiers are hard
    # compile errors — including mixes like c1 inside subscripts.
    def _quote_token(m):
        t = m.group(0)
        if len(t) == 1 or t in _TYPST_MATH_KNOWN:
            return t
        return f'"{t}"'

    parts = re.split(r'("[^"]*")', s)
    for idx in range(0, len(parts), 2):
        parts[idx] = re.sub(r'[A-Za-z][A-Za-z0-9]*', _quote_token, parts[idx])
    return ''.join(parts)


def _is_suspect_math(s: str) -> bool:
    """True if a converted math segment still looks like regex/LaTeX."""
    # our own delimiter escapes are fine; anything else backslash-y is not
    stripped = (s.replace('\\[', '').replace('\\]', '')
                 .replace('\\{', '').replace('\\}', ''))
    if '\\' in stripped:
        return True
    # a caret with no base (segment start, or after space/bracket/operator)
    if re.search(r'(?:\A|[\s(\[,+\*/=])\^', stripped):
        return True
    # regex-style character class containing ^ or backslash
    if re.search(r'\[[^\]\n]*[\^\\][^\]\n]*\]', stripped):
        return True
    return False


def _raw_literal(content: str, code: bool = False) -> str:
    """Render a segment as an inline Typst raw literal.

    code=True for use inside function argument lists (no `#` prefix)."""
    payload = content.replace('\\', '\\\\').replace('"', '\\"')
    return f'{"#" if not code else ""}raw("{payload}")'


# ---------------------------------------------------------------------------
# Markup hardening
# ---------------------------------------------------------------------------

_PAIR_TOKEN = "@PAIR{}@"
_STRONG_RE = re.compile(r'(?<![\w\*])\*(\S(?:[^*\n]*\S)?)\*(?![\w*])')
_EMPH_RE = re.compile(r'(?<![\w\\_])_(\S(?:[^_\n]*\S)?)_(?![\w*])')


def _harden_markup(seg: str) -> str:
    """Make a markup segment compile-safe: escape stray emphasis delimiters,
    fill-in-the-blank runs, hats, brackets and stray dollars.
    Escape-aware: a segment may already contain backslash escapes, and
    escaping them again would leak bare $ / _ / * into the output."""
    # collapse markdown bold **x** -> *x* before pairing, otherwise the
    # strong stash would preserve the literal double stars
    seg = re.sub(r'\*\*(\S(?:[^*\n]*\S)?)\*\*', r'*\1*', seg)

    # stash legit paired strong/emph, hardening their interiors; the raw
    # delimiters are restored after the stray-escaping below
    stashed: list[str] = []

    def _stash(m):
        delim, inner = m.group(0)[0], m.group(1)
        stashed.append(delim + _harden_markup(inner) + delim)
        return _PAIR_TOKEN.format(len(stashed) - 1)

    seg = _STRONG_RE.sub(_stash, seg)
    seg = _EMPH_RE.sub(_stash, seg)

    # fill-in-the-blank runs (_____...) become literal underscores
    seg = re.sub(r'_{3,}', lambda m: r'\_' * len(m.group()), seg)

    # escape-aware tokenise: keep existing escapes (doubling the backslash
    # before letters, which cannot be escaped in Typst markup), escape the
    # remaining special characters
    specials = '*_[]$^`'
    out = []
    k = 0
    while k < len(seg):
        ch = seg[k]
        if ch == '\\' and k + 1 < len(seg):
            nxt = seg[k + 1]
            if nxt.isalpha():
                out.append('\\\\')  # render the backslash itself
            else:
                out.append('\\' + nxt)  # keep the existing escape
            k += 2
            continue
        out.append('\\' + ch if ch in specials else ch)
        k += 1
    seg = ''.join(out)

    for i, val in enumerate(stashed):
        seg = seg.replace(_PAIR_TOKEN.format(i), val)
    return seg


def _looks_like_math(inner: str) -> bool:
    """Heuristic: does a $-delimited candidate actually contain math?

    Regex-anchored prose like $^$ or $5 and 10$ must NOT become math,
    or dollars pair up across lines and corrupt the document."""
    s = inner.strip()
    if not s or '`' in s:
        return False
    if re.search(r'[=+\^_/\\<>|]', s) and not re.search(
        r'\b(the|of|and|is|are|to|for|with|start|end|line|this|that|each)\b', s
    ):
        return True
    # short single token without spaces: 5, x_0, n!
    if ' ' not in s and re.fullmatch(r"[A-Za-z0-9_.+\-'!]+", s):
        return True
    return False


def _convert_math_pair(inner: str) -> str:
    """Render one accepted $...$ pair: converted math, or a raw literal
    if the conversion still looks like regex/LaTeX."""
    converted = convert_math_segment(inner)
    if _is_suspect_math(converted):
        return _raw_literal(inner)
    if not converted.strip():
        return ''
    return f'${converted}$'


def strip_markdown_artifacts(text: str) -> str:
    """Normalise LLM text into compile-safe Typst markup: drop markdown/code
    fences and preamble lines, convert LaTeX math inside $...$, and harden
    the surrounding markup. Guarantees no unpaired $ survives: lone dollars
    become escaped literals."""
    if not text:
        return text

    # markdown code fences (```typ ... ``` or just ``` ... ```)
    text = re.sub(r'```(?:typ|typst|latex|tex)?\s*\n?', '', text)
    # leading "Corrected ..." preamble lines
    text = re.sub(
        r'^(?:\*\*)?Corrected (?:Typst|LaTeX) document(?:\*\*)?\s*\n*',
        '', text, flags=re.IGNORECASE,
    )

    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch != '$':
            j = text.find('$', i)
            if j == -1:
                j = n
            out.append(_harden_markup(text[i:j]))
            i = j
            continue
        if text[i:i + 2] == r'\$':  # already-escaped literal dollar
            out.append(r'\$')
            i += 2
            continue
        # find the closing dollar, honouring backslash escapes
        j = i + 1
        while j < n:
            if text[j] == '\\':
                j += 2
                continue
            if text[j] == '$':
                break
            j += 1
        if j >= n:  # unpaired: literal dollar
            out.append(r'\$')
            i += 1
            continue
        inner = text[i + 1:j]
        if _looks_like_math(inner):
            out.append(_convert_math_pair(inner))
        else:
            out.append(r'\$' + _harden_markup(inner) + r'\$')
        i = j + 1
    return ''.join(out).strip()


# ---------------------------------------------------------------------------
# Content escaping (machine-supplied strings)
# ---------------------------------------------------------------------------

_CONTENT_SPECIALS = "\\#$[]*_`@<>^"


def escape_typst_content(text: str) -> str:
    """Escape characters that would start special markup in Typst content."""
    out = []
    for ch in text:
        if ch in _CONTENT_SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)
