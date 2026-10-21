"""
Deterministic Typst formatting utilities.

Handles notation table generation, section compilation, and full document
assembly.  Markup normalisation and LaTeX->Typst math conversion live in
formatter_math.  No LLM calls — pure Python.
"""

from typing import Optional

from compiler.sanitisation import sanitize_typst
from compiler.formatter_math import (
    convert_math_segment,
    _is_suspect_math,
    _raw_literal,
    strip_markdown_artifacts,
    escape_typst_content,
)


def build_notation_table(notation_list: list[dict]) -> str:
    """Build a Typst notation table from a list of {"symbol": ..., "meaning": ...} dicts.

    Returns an empty string if the list is empty or None.
    """
    if not notation_list:
        return ""

    rows = []
    for entry in notation_list:
        symbol = entry.get("symbol", "")
        meaning = entry.get("meaning", "")
        if not symbol:
            continue
        # The symbol is rendered in math mode; strip markdown-style $ signs
        # the writer may have carried over, then convert LaTeX leftovers.
        if symbol.startswith("$") and symbol.endswith("$"):
            symbol = symbol[1:-1]
        converted = convert_math_segment(symbol)
        if _is_suspect_math(converted):
            sym_cell = _raw_literal(symbol, code=True)
        else:
            sym_cell = f"${converted}$"
        meaning_cell = f"[{escape_typst_content(meaning)}]"
        rows.append(f"    {sym_cell}, {meaning_cell},")

    table_lines = [
        "#heading(numbering: none)[Notation Used in This Section]",
        "",
        "#table(",
        "  columns: (auto, 1fr),",
        "  align: (right, left),",
        "  inset: (x: 1em, y: 0.55em),",
        "  table.hline(stroke: 0.8pt),",
        "  table.header([*Symbol*], [*Meaning*]),",
        "  table.hline(stroke: 0.4pt),",
        *rows,
        "  table.hline(stroke: 0.8pt),",
        ")",
        "",
    ]
    return "\n".join(table_lines)


# ---------------------------------------------------------------------------
# Section compilation (replaces the old LLM-based Stage 2.4)
# ---------------------------------------------------------------------------

def _render_question(
    qnum: int,
    text: str,
    options: Optional[list[str]] = None,
    note: Optional[str] = None,
) -> list[str]:
    """Render one question block, optionally with MCQ options and a source note."""
    lines = [f"*Question {qnum}.* {strip_markdown_artifacts(text)}"]
    if options:
        lines.append("#enum(numbering: \"A.\", spacing: 0.9em)")
        for opt in options:
            lines.append(f"  [{strip_markdown_artifacts(str(opt))}]")
        lines.append("")
    if note:
        lines.append("#emph[" + strip_markdown_artifacts(note) + "]")
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
    Deterministically assemble theory and questions into Typst for one section.

    Each section renders as: Theory, Practice Questions, Past-Year Questions.
    Also returns the per-section answer-key lines (question numbers follow
    the per-section question counter).

    Args:
        section_title:        Title for the ``= `` heading.
        theory_text:          Typst theory from the Section Writer (uses ``===``).
        practice_questions:   [{level, text, answer, options?}] from the Question Set Builder.
        pyq_questions:        [{text, source, adapted, answer, options?}] curated candidates.
        notation:             [{symbol, meaning}] reported by the writer.
        newpage_per_question: If True, insert a page break after each question.

    Returns:
        (section_typ, answer_key_lines)
    """
    parts: list[str] = []
    answer_key: list[str] = []
    qnum = 0

    # --- Section heading + Theory ---
    parts.append(f"= {escape_typst_content(section_title)}")
    parts.append("")
    parts.append("== Theory")
    parts.append("")
    parts.append(strip_markdown_artifacts(theory_text))
    parts.append("")

    # --- Practice Questions ---
    if practice_questions:
        parts.append("#pagebreak()")
        parts.append("#heading(numbering: none)[Practice Questions]")
        parts.append("")

    for idx, q in enumerate(practice_questions):
        qnum += 1
        level = str(q.get("level", "")).upper()
        parts.append(f"// --- {level} ---")
        parts.extend(_render_question(qnum, q.get("text", ""), q.get("options")))
        answer_key.append(f"{qnum}. {q.get('answer') or '(see theory)'}")
        parts.append("")
        # No break after the final practice question: when PYQs follow, the
        # Past-Year heading below already starts on a fresh page.
        if newpage_per_question and idx < len(practice_questions) - 1:
            parts.append("#pagebreak()")
            parts.append("")

    # --- Past-Year Questions ---
    if pyq_questions:
        if practice_questions:
            parts.append("#pagebreak()")
        parts.append("#heading(numbering: none)[Past-Year Questions]")
        parts.append("")

    for idx, q in enumerate(pyq_questions):
        qnum += 1
        source = str(q.get("source") or "past exam")
        note = f"(Adapted from: {source})" if q.get("adapted") else f"(Source: {source})"
        parts.extend(_render_question(qnum, q.get("text", ""), q.get("options"), note=note))
        answer_key.append(f"{qnum}. {q.get('answer') or '(see theory)'}")
        parts.append("")
        if newpage_per_question and idx < len(pyq_questions) - 1:
            parts.append("#pagebreak()")
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
    Assemble a complete, compilable Typst document from compiled sections.

    Args:
        compiled_sections: List of Typst strings, one per section.
        section_titles:    List of section titles, parallel to compiled_sections.
        metadata:          Optional dict with keys 'title', 'author', 'date'.
        notation_data:     Optional list of lists of notation dicts per section.
        answer_key_blocks: Optional list of {"section_title", "answers": [str]}.

    Returns:
        A single string containing the full Typst document.
    """
    if metadata is None:
        metadata = {}

    title = metadata.get("title", "Learning Module")
    author = metadata.get("author", "")
    date = metadata.get("date")  # None or "\today" -> render today's date

    # --- PREAMBLE ---
    doc_meta = f'#set document(\n  title: "{_escape_string(title)}",\n'
    if author:
        doc_meta += f'  author: ({_escape_string(author)},),\n'
    doc_meta += ")\n"

    preamble = doc_meta + """
#set page(paper: "a4", margin: 2.5cm, numbering: "1")
#set text(font: ("Libertinus Serif", "New Computer Modern"), size: 12pt, lang: "en")
#set heading(numbering: "1.1.1")
#set par(justify: true)
#set enum(spacing: 1.2em)
"""

    # --- TITLE ---
    title_block = "#align(center)[\n"
    title_block += f"  #text(size: 20pt, weight: \"bold\")[{escape_typst_content(title)}]\n"
    title_block += "\n  #v(0.3em)\n"
    if date and date not in (r"\today", ""):
        title_block += f"  {escape_typst_content(date)}\n"
    else:
        title_block += '  #text(size: 12pt)[#datetime.today().display("[month repr:long] [day], [year]")]\n'
    title_block += "]\n"
    if author:
        title_block += f"\n#align(center)[{escape_typst_content(author)}]\n"

    # --- BEGIN DOCUMENT ---
    body_parts = []
    body_parts.append("")
    body_parts.append("#v(1em)")
    body_parts.append("#outline(title: [Contents])")
    body_parts.append("#pagebreak()")
    body_parts.append("")

    # --- SECTIONS ---
    for i, (section_typ, sec_title) in enumerate(
        zip(compiled_sections, section_titles)
    ):
        # Sections were stripped piecewise in compile_section; stripping again
        # here would corrupt markup produced by the markdown-conversion rules.
        cleaned = section_typ
        body_parts.append(f"// {'=' * 60}")
        body_parts.append(f"// SECTION  {sec_title}")
        body_parts.append(f"// {'=' * 60}")
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
            body_parts.append("#pagebreak()")
            body_parts.append("#heading(numbering: none)[Answer Key]")
            body_parts.append("")
            for block in answer_key_blocks:
                if not block.get("answers"):
                    continue
                body_parts.append(f"*{escape_typst_content(block['section_title'])}*")
                body_parts.append("#list(spacing: 0.6em)")
                for answer in block["answers"]:
                    body_parts.append(f"  [{strip_markdown_artifacts(str(answer))}]")
                body_parts.append("")

    # Assemble and sanitize
    full_document = preamble + title_block + "\n" + "\n".join(body_parts) + "\n"
    full_document = sanitize_typst(full_document)

    return full_document


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _escape_string(text: str) -> str:
    """Escape a Python string for use inside a Typst string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')
