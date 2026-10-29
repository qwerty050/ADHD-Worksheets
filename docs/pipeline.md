# Pipeline Overview

Lecture PDF + Knowledge Base (PYQs + reference books) -> self-study worksheet
(worksheet JSON, [WORKSHEET_JSON_SCHEMA.md](WORKSHEET_JSON_SCHEMA.md)).
Formatting the JSON into LaTeX/PDF is a separate step that the app does not
run.

```
+-------------+   +----------------------------+   +-----------------------------+
| Lecture PDF |-->| Extraction (1 + N calls)  |-->| Pedagogical JSON (schema v2)|
+-------------+   | 1. section map (deck)     |   +-----------------------------+
                  | 2. annotate (per section) |                |
                  +----------------------------+                v
+-------------+   +----------------------------+   +-----------------------------+
|  .cmkb KB   |-->| Generation (2 calls/sec)  |-->| worksheet.json (schema v1)  |
| PYQs+books  |   | A. section writer         |   | theory + practice + PYQs    |
+-------------+   | B. question set builder   |   | + answers, no formatting    |
                  +----------------------------+   +-----------------------------+
```

## Extraction

| Stage | Function | Model (env) | LLM calls | Output |
|---|---|---|---|---|
| 1. Section map | `extract_section_map` (extraction/stages.py) | `MODEL_EXTRACTION`, max 16384 output tokens | 1 if the deck text fits `EXTRACT_BUDGET_CHARS` (300k chars, ~75k tokens); otherwise 1 per page-range chunk | `{section_map: [ExtractedSection]}` |
| 2. Annotate | `annotate_section` | `MODEL_PEDAGOGY`, max 8192 output tokens | 1 per section | `SectionAnnotation` (objectives, misconceptions, worked-example spec, embedded questions) |
| merge | `run_extraction_pipeline` | - | 0 (deterministic) | pedagogical JSON (list of sections) |

Every LLM response is validated against a pydantic model with bounded repair
retries; failures **raise** (never cached, never silently degraded). Unreadable
or text-less PDFs raise. Page-aware reading (`--- Page N ---` markers) via
PyMuPDF.

## Generation

Per section, exactly **two** LLM calls:

1. **Call A - Section Writer** (`write_section`, `MODEL_WRITER`, max 16384
   output tokens): structured theory (`motivation`, `intuition`,
   `formal_content`, `worked_example` {problem, steps, answer, insight} or
   null, `key_takeaway`) in Markdown with TeX math, the notation it actually
   used, and a 3-4 sentence summary. LaTeX sectioning commands and
   unescaped backslashes (form-feed/backspace characters) in the text fail
   validation and go through the repair retries.
   Inputs: section content, book context, the student profile (one merged
   block: past-lecture summaries + this run's summaries, capped at the most
   recent 600 words), the questions to
   prepare for (PYQ text + topic only - answers stripped, capped at 10,
   deferred rescues included), objectives + misconceptions.
2. **Call B - Question Set Builder** (`build_question_set`, `MODEL_QUESTIONS`,
   max 16384 output tokens): the practice
   ladder (recall -> evaluate), curation of candidates (include / adapt /
   defer with reasons), answers for everything, MCQ conversion in objective
   mode. Judged against the theory actually written (ground truth).
   Candidates are PYQs first, then deferred items from the previous section,
   then the lecture's embedded questions, capped at 15.

Everything else is deterministic:

- **Rolling context** = append of Call-A summaries (no LLM call).
- **Assemble** (`generation/worksheet.py`: `build_section`,
  `build_worksheet`): one section record per pedagogical section (title,
  topics, objectives, notation, theory, numbered practice and past-year
  questions with their answers, summary), plus the questions every section
  deferred. Written as JSON to `--out`. No formatting happens here.
  `compiler/` (the old LaTeX formatter) is no longer called by the pipeline.
- **Memory commit**: `kb.update` (section + summary embedding; the
  `sections.latex` column now stores the section's worksheet JSON) and
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

`PipelineCache` (shared/cache.py) files in `.pipeline_cache/` (relative to
the working directory) are keyed by input filename + content hash +
kb/lecture suffix + cache version (`CACHE_VERSION`), so changed inputs or
pipeline upgrades never serve stale results. `--fresh` (`run`, `generate`)
ignores the cache for a run; `extract` and the web API always use it. Only
validated LLM output is ever cached. Per section the cache holds the steps
`annotate`, `writer`, `questions` and `memory_updated`. `CACHE_VERSION` 3
(structured writer output) ignores every older cache file.

## Providers

`LLM_PROVIDER` selects ollama | anthropic | openai | gemini (shared/llm.py).
All JSON generation goes through `generate_json` (pydantic-validated, with
repair retries). Truncation (`stop_reason=max_tokens` etc.) raises instead of
producing broken JSON on Anthropic, OpenAI and Gemini; on Ollama a truncated
reply fails validation instead. Embeddings always run locally via Ollama
(`EMBED_MODEL`), regardless of provider - KB files stay portable.

The KB's own LLM calls (question tagging and topic aliases with `TAG_MODEL`,
PageIndex traversal with `PAGEINDEX_MODEL`) use the same provider client.
PageIndex tree building at ingest uses the vendored client in
`cmkb/pageindex/utils.py`, which only supports `ollama` and `openai` (OpenAI
key from `CHATGPT_API_KEY`).

## Memory loop

1. Build a KB once: `memory create` -> `ingest questions` -> `ingest pdf` -> `cluster`.
2. Generate worksheets with `--kb` (each run commits sections + marks PYQs used).
3. Update the KB any time: add more question JSONs / books, re-cluster
   (`/kb/manage` in the web UI, or the cmkb CLI). Question re-ingest is
   idempotent per (exam, qid); re-clustering rebuilds only pyq-sourced
   taxonomy and relinks lecture/section associations by canonical name.
