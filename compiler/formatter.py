"""
Deterministic LaTeX formatting utilities.

Handles markdown artifact stripping, notation table generation, section
compilation, and full document assembly.  No LLM calls — pure Python.
"""

import re
from typing import Optional

from compiler.sanitisation import sanitize_latex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_markdown_artifacts(text: str) -> str:
    """Remove stray markdown formatting that LLMs sometimes inject into LaTeX output."""
    # Remove markdown code fences (```latex ... ``` or just ``` ... ```)
    text = re.sub(r'```(?:latex|tex)?\s*\n?', '', text)

    # Remove standalone markdown bold markers only when they wrap text
    # but NOT inside LaTeX commands.
    text = re.sub(r'(?<![\\\*])\*\*([^*]+)\*\*', r'\1', text)

    # Remove markdown italic markers (single *)
    text = re.sub(r'(?<![\\\*])\*([^*]+)\*(?!\*)', r'\1', text)

    # Remove leading "Corrected LaTeX document" or similar LLM preamble lines
    text = re.sub(
        r'^(?:\*\*)?Corrected LaTeX document(?:\*\*)?\s*\n*',
        '', text, flags=re.IGNORECASE,
    )

    # Fix double-backslash before LaTeX commands.
    # LLMs often produce \\section, \\textbf, \\begin, etc.
    # Collapse \\ followed by a letter into a single \ + letter.
    # Preserves legitimate \\ (line breaks) since those are followed
    # by whitespace/newline/[, not a letter.
    text = re.sub(r'\\\\([a-zA-Z])', r'\\\1', text)

    return text.strip()


def build_notation_table(notation_list: list[dict]) -> str:
    """Build a LaTeX notation table from a list of {"symbol": ..., "meaning": ...} dicts.

    Returns an empty string if the list is empty or None.
    """
    if not notation_list:
        return ""

    rows = []
    for entry in notation_list:
        symbol = entry.get("symbol", "")
        meaning = entry.get("meaning", "")
        if symbol and not symbol.startswith("$"):
            symbol = f"${symbol}$"
        rows.append(f"    {symbol} & {meaning} \\\\")

    table_lines = [
        r"\subsection*{Notation Used in This Section}",
        r"\begin{tabular}{@{}ll@{}}",
        r"\toprule",
        r"Symbol & Meaning \\ \midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\vspace{1em}",
        "",
    ]
    return "\n".join(table_lines)


# ---------------------------------------------------------------------------
# Section compilation (replaces the old LLM-based Stage 2.4)
# ---------------------------------------------------------------------------

def compile_section(
    section_title: str,
    theory_text: str,
    hots_questions: list[str],
    extracted_questions: list[str],
    newpage_per_question: bool = True,
) -> str:
    """
    Deterministically assemble theory and questions into a single LaTeX section.

    Args:
        section_title:        Title for the ``\\section{}`` heading.
        theory_text:          LaTeX string produced by Stage 2.1.
        hots_questions:       List of LaTeX question strings from Stage 2.2.
        extracted_questions:  List of LaTeX question strings from Stage 2.3.
        newpage_per_question: If True, insert ``\\newpage`` after each question.

    Returns:
        A LaTeX string for the entire section.
    """
    parts: list[str] = []

    # --- Section heading ---
    parts.append(f"\\section{{{section_title}}}")
    parts.append("")

    # --- Theory ---
    cleaned_theory = strip_markdown_artifacts(theory_text)
    parts.append(cleaned_theory)
    parts.append("")

    # --- Questions ---
    all_questions = list(hots_questions) + list(extracted_questions)

    if all_questions:
        parts.append("\\newpage")
        parts.append("\\subsection*{Questions}")
        parts.append("")

        for idx, q in enumerate(all_questions):
            cleaned_q = strip_markdown_artifacts(q)

            # Extract (LEVEL) tag if present and place as LaTeX comment
            level = None
            level_match = re.match(r'^\(([^)]+)\)\s*', cleaned_q)
            if level_match:
                level = level_match.group(1)
                cleaned_q = cleaned_q[level_match.end():]
                parts.append(f"% --- {level.upper()} ---")

            parts.append("\\begin{question}")
            if level:
                parts.append(f"({level}) {cleaned_q}")
            else:
                parts.append(cleaned_q)
            parts.append("\\end{question}")
            parts.append("")

            if newpage_per_question and idx < len(all_questions) - 1:
                parts.append("\\newpage")
                parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Full document assembly (Stage 3)
# ---------------------------------------------------------------------------

def format_document(
    compiled_sections: list[str],
    section_titles: list[str],
    metadata: dict = None,
    notation_data: Optional[list[list[dict]]] = None,
) -> str:
    """
    Assemble a complete, compilable LaTeX document from compiled sections.

    Args:
        compiled_sections: List of LaTeX strings, one per section.
        section_titles:    List of section titles, parallel to compiled_sections.
        metadata:          Optional dict with keys 'title', 'author', 'date'.
        notation_data:     Optional list of lists of notation dicts per section.

    Returns:
        A single string containing the full LaTeX document.
    """
    if metadata is None:
        metadata = {}

    title = metadata.get("title", "Learning Module")
    author = metadata.get("author", "")
    date = metadata.get("date", r"\today")

    # --- PREAMBLE ---
    preamble = r"""\documentclass[12pt, a4paper]{article}

% --- Encoding & Fonts ---
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}

% --- Mathematics ---
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsthm}
\usepackage{mathtools}
\newcounter{question}[section]
\renewcommand{\thequestion}{\thesection.\arabic{question}}

\newenvironment{question}
  {\refstepcounter{question}\par\noindent\textbf{Question \thequestion:}}
  {\par}

% --- Layout ---
\usepackage[margin=1in]{geometry}

% --- Lists ---
\usepackage{enumitem}

% --- Tables ---
\usepackage{booktabs}
\usepackage{array}

% --- Graphics ---
\usepackage{graphicx}

% --- Headers / Footers ---
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\leftmark}
\fancyhead[R]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% --- Hyperlinks & Cross-references ---
\usepackage[colorlinks=true, linkcolor=blue, urlcolor=blue, citecolor=blue]{hyperref}

% --- Misc ---
\usepackage{xcolor}

% --- Custom commands (safety definitions) ---
\providecommand{\operatorname}[1]{\mathop{\mathrm{#1}}\nolimits}
"""

    # --- TITLE ---
    title_block = f"\\title{{{sanitize_latex(title)}}}\n"
    if author:
        title_block += f"\\author{{{sanitize_latex(author)}}}\n"
    else:
        title_block += "\\author{}\n"
    title_block += f"\\date{{{date}}}\n"

    # --- BEGIN DOCUMENT ---
    body_parts = []
    body_parts.append(r"\begin{document}")
    body_parts.append("")
    body_parts.append(r"\maketitle")
    body_parts.append(r"\thispagestyle{empty}")
    body_parts.append(r"\newpage")
    body_parts.append("")
    body_parts.append(r"\tableofcontents")
    body_parts.append(r"\newpage")
    body_parts.append("")

    # --- SECTIONS ---
    for i, (section_latex, sec_title) in enumerate(
        zip(compiled_sections, section_titles)
    ):
        cleaned = strip_markdown_artifacts(section_latex)
        if i > 0:
            body_parts.append(r"\newpage")
        body_parts.append(f"% {'=' * 60}")
        body_parts.append(f"% SECTION  {sec_title}")
        body_parts.append(f"% {'=' * 60}")
        body_parts.append("")

        # Insert notation table if data is available for this section
        if notation_data and i < len(notation_data):
            notation_table = build_notation_table(notation_data[i])
            if notation_table:
                body_parts.append(notation_table)

        body_parts.append(cleaned)
        body_parts.append("")

    # --- END DOCUMENT ---
    body_parts.append(r"\end{document}")

    # Assemble and sanitize
    full_document = (
        preamble + "\n" + title_block + "\n" + "\n".join(body_parts) + "\n"
    )
    full_document = sanitize_latex(full_document)

    return full_document


# ---------------------------------------------------------------------------
# Context summary (deterministic, no LLM)
# ---------------------------------------------------------------------------

def generate_context_summary(
    section_titles: list[str],
    section_topics: list[list[str]],
) -> str:
    """Generate a simple programmatic context summary."""
    lines = [
        "Context Summary",
        "=" * 40,
        f"Total sections covered: {len(section_titles)}",
        "",
    ]
    for i, (title, topics) in enumerate(zip(section_titles, section_topics)):
        lines.append(f"Section {i + 1}: {title}")
        if topics:
            lines.append(f"  Topics: {', '.join(topics)}")
    lines.append("")
    lines.append(
        "This context can be passed as input to the next session "
        "to maintain continuity."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
