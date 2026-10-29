# Worksheet JSON Schema (v1)

The generation pipeline (`generate` / `run` commands, or the web app) writes
the worksheet as **one JSON file**. It holds the content of every section and
no formatting. Turning it into LaTeX, a PDF or anything else is a separate
formatting step that reads this file.

The pydantic models in `generation/worksheet.py` are the source of truth.
Print the machine-readable JSON Schema with:

```bash
python -c "import json; from generation.worksheet import Worksheet; print(json.dumps(Worksheet.model_json_schema(), indent=2))"
```

Input to generation is the [Pedagogical JSON (v2)](PEDAGOGICAL_JSON_SCHEMA.md).

## Text format

Every free-text field (theory parts, worked-example parts, question text,
options, answers, notation meanings, summary) is **Markdown with TeX math**
(`content_format: "markdown+tex"`):

- Inline math in `$...$`, display math in `$$...$$`.
- Markdown for emphasis, lists and tables.
- No LaTeX outside math. Document structure (headings, page breaks, question
  numbering layout, the answer key) is the formatter's job. The writer output
  is rejected (and repaired by the model) if it contains `\section`,
  `\subsection`, `\subsubsection`, `\chapter`, `\part`, `\documentclass` or
  `\begin{document}`, or a form-feed/backspace character (the sign of an
  unescaped backslash such as `"\frac"` in the model's JSON).
- `notation[].symbol` is TeX math **without** `$` delimiters (e.g. `\mathbf{w}`).

Text is UTF-8 and is not sanitised. A formatter must escape or map characters
for its target (for LaTeX, see `compiler/sanitisation.py`).

PYQ text is copied from the knowledge base and may use whatever markup the
original question file used.

## Example

```json
{
  "schema_name": "adhd-worksheet",
  "schema_version": 1,
  "content_format": "markdown+tex",
  "title": "L01",
  "lecture_id": "L01",
  "generated_at": "2026-10-29T10:15:00+00:00",
  "objective_mode": false,
  "render_hints": {"newpage_per_question": true},
  "sections": [
    {
      "index": 1,
      "title": "1. Cosine Similarity",
      "topics": ["cosine similarity", "vector space model"],
      "learning_objectives": ["Student can compute the cosine similarity of two vectors."],
      "notation": [
        {"symbol": "\\mathbf{a}", "meaning": "a document vector"},
        {"symbol": "\\lVert \\mathbf{a} \\rVert", "meaning": "the length (Euclidean norm) of $\\mathbf{a}$"}
      ],
      "theory": {
        "motivation": "Search engines must decide which documents are *about* the same thing as a query.",
        "intuition": "Two documents are similar when their word-count arrows point the same way, whatever their length.",
        "formal_content": "For vectors $\\mathbf{a}, \\mathbf{b}$:\n\n$$\\cos\\theta = \\frac{\\mathbf{a} \\cdot \\mathbf{b}}{\\lVert \\mathbf{a} \\rVert \\, \\lVert \\mathbf{b} \\rVert}$$",
        "worked_example": {
          "problem": "Find the cosine similarity of $\\mathbf{a} = (1, 2)$ and $\\mathbf{b} = (2, 4)$.",
          "steps": [
            "Dot product: $1 \\cdot 2 + 2 \\cdot 4 = 10$.",
            "Lengths: $\\lVert \\mathbf{a} \\rVert = \\sqrt{5}$, $\\lVert \\mathbf{b} \\rVert = \\sqrt{20}$.",
            "Divide: $10 / (\\sqrt{5} \\cdot \\sqrt{20}) = 10 / 10 = 1$."
          ],
          "answer": "$1$",
          "insight": "Vectors that differ only in length have similarity 1."
        },
        "key_takeaway": "Cosine similarity compares direction, not length."
      },
      "practice_questions": [
        {"number": 1, "level": "recall", "text": "Write the formula for cosine similarity.", "options": null, "answer": "$\\frac{\\mathbf{a} \\cdot \\mathbf{b}}{\\lVert \\mathbf{a} \\rVert \\lVert \\mathbf{b} \\rVert}$"}
      ],
      "past_year_questions": [
        {"number": 2, "text": "Why is cosine similarity preferred over Euclidean distance for documents?", "source": "Endsem 2024 Q3", "adapted": false, "candidate_id": "kb:42", "options": null, "answer": "It ignores document length."}
      ],
      "summary": "This section defined cosine similarity and computed it for two short vectors."
    }
  ],
  "unplaced_questions": [
    {"text": "Derive the skip-gram objective.", "source": "Midsem 2023 Q5", "reason": "word2vec is not taught in this lecture"}
  ]
}
```

## Top level

| Field | Type | Meaning |
|---|---|---|
| `schema_name` | `"adhd-worksheet"` | Identifies the file type. |
| `schema_version` | `1` | Bumped on any breaking change to this contract. |
| `content_format` | `"markdown+tex"` | Markup used by all text fields (see above). |
| `title` | string | Module name, from the output file name (`output/L01.json` gives `L01`). |
| `lecture_id` | string or null | `--lecture-id` / the web lecture ID. |
| `generated_at` | string | UTC timestamp, ISO 8601. |
| `objective_mode` | bool | `--objective`: every question has 4 `options` and `answer` is a letter `A`-`D`. |
| `render_hints.newpage_per_question` | bool | Presentation preference from `--no-newpage` / the web toggle. Content is the same either way. |
| `sections` | list | One entry per pedagogical section, in order. |
| `unplaced_questions` | list of `{text, source, reason}` | Candidates every section deferred. They stay unused in the KB and come back next run. |

## Section

| Field | Type | Meaning |
|---|---|---|
| `index` | int | 1-based position. |
| `title` | string | `section_title` from the pedagogical JSON. |
| `topics` | list of string | `topics` + `subtopics` from the pedagogical JSON. |
| `learning_objectives` | list of string | From the pedagogical JSON. |
| `notation` | list of `{symbol, meaning}` | Every symbol the theory introduced. |
| `theory.motivation` | string | Why the concept exists. Never empty. |
| `theory.intuition` | string | The idea in plain words, before the maths. Never empty. |
| `theory.formal_content` | string | Definitions and formulas. Never empty. |
| `theory.worked_example` | object or null | `{problem, steps: [string, ...], answer, insight}`; null when the content is not numeric or procedural. `steps` has at least one item. |
| `theory.key_takeaway` | string | The one thing to remember. Never empty. |
| `practice_questions` | list | `{number, level, text, options, answer}`; `level` is `recall`, `understand`, `apply`, `analyse` or `evaluate` (the ladder order). |
| `past_year_questions` | list | `{number, text, source, adapted, candidate_id, options, answer}`. `adapted: true` means the wording was changed. `candidate_id` is `kb:<pk>` for a KB question, `lec:<section>:<n>` for a question from the lecture slides. |
| `summary` | string | 3-4 sentences on what the section taught (also stored in the KB). |

`number` runs from 1 per section, practice questions first, then past-year
questions. `answer` can be an empty string when the model gave none; the
formatter decides how to show that. Answers sit with their questions; whether
they are printed inline or in an end-of-document answer key is a formatting
choice.
