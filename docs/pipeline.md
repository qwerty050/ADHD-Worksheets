# Pipeline Overview

Lecture PDF + Knowledge Base (PYQs + reference books) -> self-study worksheet (.typ).

```
+-------------+   +----------------------------+   +-----------------------------+
| Lecture PDF |-->| Extraction (1 + N calls)  |-->| Pedagogical JSON (schema v2)|
+-------------+   | 1. section map (deck)     |   +-----------------------------+
                  | 2. annotate (per section) |                |
                  +----------------------------+                v
+-------------+   +----------------------------+   +-----------------------------+
|  .cmkb KB   |-->| Generation (2 calls/sec)  |-->| worksheet.typ               |
| PYQs+books  |   | A. section writer         |   | theory + practice + PYQs    |
+-------------+   | B. question set builder   |   | + answer key                |
                  +----------------------------+   +-----------------------------+
```

## Extraction

| Stage | Function | LLM calls | Output |
|---|---|---|---|
| 1. Section map | `extract_section_map` (extraction/stages.py) | 1 (+1 per chunk if the deck exceeds ~300k chars) | `{section_map: [ExtractedSection]}` |
| 2. Annotate | `annotate_section` | 1 per section | `SectionAnnotation` (objectives, misconceptions, worked-example spec, embedded questions) |
| merge | `run_extraction_pipeline` | 0 (deterministic) | pedagogical JSON (list of sections) |

Every LLM response is validated against a pydantic model with bounded repair
retries; failures **raise** (never cached, never silently degraded). Unreadable
or text-less PDFs raise. Page-aware reading (`--- Page N ---` markers) via
PyMuPDF.

## Generation

Per section, exactly **two** LLM calls:

1. **Call A - Section Writer** (`write_section`): theory Typst markup
   (Motivation -> Intuition -> Formal Content -> Worked Example -> Key
   Takeaway), the notation it actually used, and a 3-4 sentence summary.
   Inputs: section content, book context, the student profile (one merged
   block: past-lecture summaries + this run's summaries), the questions to
   prepare for (PYQ text + topic only - answers stripped, capped at 10,
   deferred rescues included), objectives + misconceptions.
2. **Call B - Question Set Builder** (`build_question_set`): the practice
   ladder (recall -> evaluate), curation of candidates (include / adapt /
   defer with reasons), answers for everything, MCQ conversion in objective
   mode. Judged against the theory actually written (ground truth).

Everything else is deterministic:

- **Rolling context** = append of Call-A summaries (no LLM call).
- **Compile** (`compile_section`): `\subsection{Theory}`,
  `\subsection*{Practice Questions}`, `\subsection*{Past-Year Questions}`,
  per-section notation tables, document-end **Answer Key**.
- **Memory commit**: `kb.update` (section + summary embedding) and
  `kb.mark_questions_used` (PYQ usage tracking), idempotent via the
  `memory_updated` cache guard on resume.
- Deferred questions that no section claims are logged at the end of the run
  (and stay unmarked in memory, so they resurface next time).

## PYQ reuse

`kb.query(..., reuse=...)`:

- `prefer` (default): serve never-used PYQs first; fall back to used ones
  (flagged `repeat: true`) only when a topic's fresh pool is empty.
- `never`: hard-exclude used questions.

Usage is recorded per (question, lecture) in the `question_usage` table when a
worksheet commits a section containing that PYQ. Within a single run,
candidates are deduped by (source, qid) so two similar sections cannot both
claim the same question. Surfaces: CLI `--no-reuse`, API `?reuse=never`,
web toggle "Never repeat PYQs".

## Caching

`PipelineCache` (shared/cache.py) files in `.pipeline_cache/` are keyed by
input filename + content hash + kb/lecture suffix + cache version, so changed
inputs or pipeline upgrades never serve stale results. `--fresh` ignores the
cache for a run. Only validated LLM output is ever cached.

## Providers

`LLM_PROVIDER` selects ollama | anthropic | openai | gemini (shared/llm.py).
All JSON generation goes through `generate_json` (pydantic-validated, with
repair retries). Truncation (`stop_reason=max_tokens` etc.) raises instead of
producing broken JSON. Embeddings always run locally via Ollama
(`EMBED_MODEL`), regardless of provider - KB files stay portable.

## Memory loop

1. Build a KB once: `memory create` -> `ingest questions` -> `ingest pdf` -> `cluster`.
2. Generate worksheets with `--kb` (each run commits sections + marks PYQs used).
3. Update the KB any time: add more question JSONs / books, re-cluster
   (`/kb/manage` in the web UI, or the cmkb CLI). Question re-ingest is
   idempotent per (exam, qid); re-clustering rebuilds only pyq-sourced
   taxonomy and relinks lecture/section associations by canonical name.
