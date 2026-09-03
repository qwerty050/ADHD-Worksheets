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

    # Remove standalone markdown bold/italic markers only when they wrap text,
    # but never inside LaTeX commands. A `*` immediately following a word
    # character is a LaTeX starred command (\subsection*), not emphasis.
    text = re.sub(r'(?<![\w\\\*])\*\*([^*]+?)\*\*(?![\w*])', r'\1', text)

    # Remove markdown italic markers (single *)
    text = re.sub(r'(?<![\w\\\*])\*([^*]+?)\*(?![\w*])', r'\1', text)

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

def _render_question(text: str, options: Optional[list[str]] = None, note: Optional[str] = None) -> list[str]:
    """Render one question environment, optionally with MCQ options and a source note."""
    lines = ["\\begin{question}"]
    cleaned_q = strip_markdown_artifacts(text)
    lines.append(cleaned_q)
    if options:
        lines.append(r"\begin{enumerate}[label=\Alph*,itemsep=1pt]")
        for opt in options:
            lines.append(f"  \\item {strip_markdown_artifacts(str(opt))}")
        lines.append(r"\end{enumerate}")
    lines.append("\\end{question}")
    if note:
        lines.append(r"\par\smallskip\noindent\textit{" + strip_markdown_artifacts(note) + "}")
        lines.append("")
    return lines


def compile_section(
    section_title: str,
    theory_text: str,
    practice_questions: list[dict],
    pyq_questions: list[dict],
    notation: Optional[list[dict]] = None,
    newpage_per_question: bool = True,
) -> tuple[str, list[str]]:
    """
    Deterministically assemble theory and questions into LaTeX for one section.

    Each section renders as: Theory, Practice Questions, Past-Year Questions.
    Also returns the per-section answer-key lines (question numbers follow the
    LaTeX question counter, which is sequential per section).

    Args:
        section_title:        Title for the ``\\section{}`` heading.
        theory_text:          LaTeX theory from the Section Writer (uses \\subsubsection).
        practice_questions:   [{level, text, answer, options?}] from the Question Set Builder.
        pyq_questions:        [{text, source, adapted, answer, options?}] curated candidates.
        notation:             [{symbol, meaning}] reported by the writer.
        newpage_per_question: If True, insert ``\\newpage`` after each question.

    Returns:
        (section_latex, answer_key_lines)
    """
    parts: list[str] = []
    answer_key: list[str] = []
    qnum = 0

    # --- Section heading + Theory ---
    parts.append(f"\\section{{{section_title}}}")
    parts.append("")
    parts.append("\\subsection{Theory}")
    parts.append("")
    parts.append(strip_markdown_artifacts(theory_text))
    parts.append("")

    # --- Practice Questions ---
    if practice_questions:
        parts.append("\\newpage")
        parts.append("\\subsection*{Practice Questions}")
        parts.append("")

    for idx, q in enumerate(practice_questions):
        qnum += 1
        level = str(q.get("level", "")).upper()
        parts.append(f"% --- {level} ---")
        parts.extend(_render_question(q.get("text", ""), q.get("options")))
        answer_key.append(f"{qnum}. {q.get('answer') or '(see theory)'}")
        parts.append("")
        if newpage_per_question and idx < len(practice_questions) + len(pyq_questions) - 1:
            parts.append("\\newpage")
            parts.append("")

    # --- Past-Year Questions ---
    if pyq_questions:
        if practice_questions:
            parts.append("\\newpage")
        parts.append("\\subsection*{Past-Year Questions}")
        parts.append("")

    for idx, q in enumerate(pyq_questions):
        qnum += 1
        source = str(q.get("source") or "past exam")
        note = f"(Adapted from: {source})" if q.get("adapted") else f"(Source: {source})"
        parts.extend(_render_question(q.get("text", ""), q.get("options"), note=note))
        answer_key.append(f"{qnum}. {q.get('answer') or '(see theory)'}")
        parts.append("")
        if newpage_per_question and idx < len(pyq_questions) - 1:
            parts.append("\\newpage")
            parts.append("")

    return "\n".join(parts), answer_key


# ---------------------------------------------------------------------------
# Full document assembly (Stage 3)
# ---------------------------------------------------------------------------

def format_document(
    compiled_sections: list[str],
    section_titles: list[str],
    metadata: dict = None,
    notation_data: Optional[list[list[dict]]] = None,
    answer_key_blocks: Optional[list[dict]] = None,
) -> str:
    """
    Assemble a complete, compilable LaTeX document from compiled sections.

    Args:
        compiled_sections: List of LaTeX strings, one per section.
        section_titles:    List of section titles, parallel to compiled_sections.
        metadata:          Optional dict with keys 'title', 'author', 'date'.
        notation_data:     Optional list of lists of notation dicts per section.
        answer_key_blocks: Optional list of {"section_title", "answers": [str]}.

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

    # --- ANSWER KEY ---
    if answer_key_blocks:
        has_answers = any(block.get("answers") for block in answer_key_blocks)
        if has_answers:
            body_parts.append(r"\newpage")
            body_parts.append(r"\section*{Answer Key}")
            body_parts.append("")
            for block in answer_key_blocks:
                if not block.get("answers"):
                    continue
                body_parts.append(f"\\textbf{{{sanitize_latex(block['section_title'])}}}")
                body_parts.append(r"\begin{itemize}[itemsep=0pt]")
                for answer in block["answers"]:
                    body_parts.append(f"  \\item {strip_markdown_artifacts(str(answer))}")
                body_parts.append(r"\end{itemize}")
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
# Internal helpers
# ---------------------------------------------------------------------------
