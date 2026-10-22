# Changelog

## 2026-10-21 — Docs and config housekeeping

Docs and non-behavioural config only. No code, prompt, schema, cache-version,
default-model, CLI or API changes.

### Corrected

- **README.md**: setup now says `cp .env.example .env` and lists the real
  default models (`nomic-embed-text`, `gemma3n:e4b`, `gpt-oss:120b-cloud`)
  instead of `ollama pull llama3`. It also explains that `-cloud` models need
  `ollama signin`, that models are switched through `.env` (not by editing
  code), and gives the Node.js version Vite 8 needs. Output is described as
  `.tex` (the app does not compile PDFs). The theory structure matches the
  writer prompt, and the "everyday analogy" claims (removed in v2) are gone.
  Added links to `cmkb/README.md`, `web/README.md` and a note on `example/`.
- **docs/installation.md**: replaced the retired `MODEL_THEORY`,
  `MODEL_QUESTION_EXTRACT`, `MODEL_QUESTION_FILTER`, `MODEL_CONTEXT_SUMMARY`
  and `MODEL_REVIEW` knobs with the real variables. Added a table of every
  environment variable the code reads, with its default. Noted that Ollama is
  always required (for embeddings), that switching provider means renaming
  every model variable, and that `memory create` records `nomic-embed-text`
  unless you pass `--embed-model`. Added the Ollama pull steps and the web app
  install.
- **docs/usage.md**: removed the non-existent `--no-review` flag. Documented
  `--no-reuse`, `--fresh`, `--kb`/`--lecture-id`/`--out`, that `run` writes
  the JSON next to the `.tex`, that `--kb` updates the KB in place, and the
  `memory` subcommands that were missing (`query`, `debug-topic`,
  `ingest lecture`, `ingest section`, `stats`). Added the HTTP API routes and
  the web app's session-copy behaviour.
- **docs/chatbot_workflow.md**: rewritten to the v2 two-prompt flow, word for
  word the same as the in-app AI Guide (`web/src/pages/GuidePage.tsx`). The old
  three-step v1 flow is gone. Model versions are replaced by generic wording.
- **docs/pyq_chatbot_workflow.md**: versioned model names replaced by generic
  wording; ingest/cluster behaviour clarified.
- **docs/pipeline.md**: Stage 1 call count (one call per page-range chunk
  for decks over 300k chars, not "+1"). Added the model variable and output
  limit per stage, the 15-candidate and 600-word caps, cache step names, which
  commands honour `--fresh`, and how KB/PageIndex LLM calls are routed.
- **docs/PEDAGOGICAL_JSON_SCHEMA.md**: `dependency_order` is re-assigned only
  by extraction; added a link to the chatbot workflow.
- **cmkb/README.md**: `PAGEINDEX_MODEL` default is `gemma3n:e4b` (was
  `gemma4:e4b`). The CLI is `main_cli.py memory` / `cmkb/cli.py` (there is no
  `cmkb_cli.py`). Documented `query(..., reuse=)`, the real shape of
  `questions`, `mark_questions_used`, `kb_stats`/`usage_stats`, and that
  `already_covered` excludes the current lecture.
- **web/README.md**: replaced the Vite template README with a project one
  (how to run it, `src/api.ts`, `VITE_API_URL`).
- **requirements.txt**: added `PyYAML` (`cmkb/pageindex/utils.py` imports
  `yaml`; the 2026-09-03 entry said it was added, but it was not). Noted
  `tiktoken` as optional.
- **.env.example**: documented `OLLAMA_API_URL`, `CHATGPT_API_KEY`
  (`Ollama_API_KEY`), `OLLAMA_MODEL` and `VITE_API_URL` as commented
  optional entries. Added notes on cloud models and on switching provider.
  The active values are unchanged.

### Known issues now documented (not fixed here)

- `memory ingest pdf --mode page_index` (and the web "Detailed indexing"
  option) fails with a `NameError` in `cmkb/ingest_pdf.py`. The 2026-09-03
  entry's "correct `page_index_main` entry point" fixed the import but not
  the call.
- `memory stats` has no KB path argument and cannot run.
- `memory ingest lecture` fails on the bare-list JSON that `extract` writes.

## 2026-09-03 — Pipeline overhaul: 2-call generation, PYQ memory, multi-provider LLMs

A full revision of the worksheet pipeline. Output structure is preserved
(per-section theory + practice questions + PYQs), but the machinery feeding it
was rebuilt: **6 LLM calls per section → 2**, short prompts with only inputs
that are actually used, pydantic-validated structured outputs, PYQ usage
tracking in the memory, and OpenAI/Anthropic/Gemini support alongside Ollama.

### Generation (rewritten)

- **Two LLM calls per section** instead of six:
  - **Call A — Section Writer** (`generation/stages.py:write_section`): theory
    LaTeX (Motivation → Intuition → Formal Content → Worked Example → Key
    Takeaway), the notation it actually used (fixes notation-table drift), and
    a 3–4 sentence summary. Returns structured JSON.
  - **Call B — Question Set Builder** (`build_question_set`): writes the
    practice ladder (recall → evaluate), curates candidate PYQs/lecture
    questions (include / adapt / defer with reasons), produces answers for
    everything, and converts to MCQs in objective mode. Judged against the
    theory actually written. Returns structured JSON.
- **Eliminated stages**: separate HOTS-generation call, question-filter call,
  review pass (its critical checks became hard constraints in Call B),
  rolling-context LLM call, and section-summary LLM call. Rolling context is
  now a deterministic append of writer summaries; the summary doubles as the
  memory-commit summary.
- **PYQs feed the theory** (`prepare-for` input): the writer sees matched
  question text (answers/options stripped, capped at 10, deferred rescues
  included) and must teach the concepts they require — even beyond the slide
  content. This makes sections self-contained (e.g. a cosine-similarity
  section now actually covers word2vec/skip-gram/CBOW when the PYQs ask
  about them).
- **Compiler** now emits `Theory` / `Practice Questions` /
  `Past-Year Questions` subsections per section plus a document-end
  **Answer Key** (previously question answers were silently dropped and MCQ
  mode had no key at all). Fixed a latent regex bug where the markdown
  stripper destroyed starred `\subsection*` commands.
- Model config reduced from 5 knobs to 2: `MODEL_WRITER`, `MODEL_QUESTIONS`.

### Extraction (rewritten)

- **3 calls → 1 + N small per-section calls**: Stage 1 produces the section
  map (page-aware `--- Page N ---` input, chunked if the deck exceeds the
  token budget); Stage 2 annotates each section (objectives, misconceptions,
  worked-example spec, embedded questions) in one small call per section.
- Every LLM response is **validated against pydantic models** with bounded
  repair retries; failures **raise** instead of silently caching empty
  results (previously a failed parse produced an empty worksheet that was
  cached forever). Unreadable or text-less PDFs raise instead of becoming
  prompt content.
- Schema **v2** (`docs/PEDAGOGICAL_JSON_SCHEMA.md`): dropped
  `teach_approach`, `opening_analogy`, `prerequisite_bridge`,
  `question_prompts`, `notation_introduced`, `mapped_sections` bookkeeping.
  In-app AI Guide prompts updated to match.

### Memory (cmkb)

- **PYQ usage tracking**: new `question_usage` table (migrated on KB load).
  `kb.query(reuse=...)` — `prefer` (default) serves never-used PYQs first and
  falls back to used ones flagged `repeat: true` when a topic pool is dry;
  `never` hard-excludes them. Usage is marked only for included/adapted
  questions, idempotent per (question, lecture). Surfaces: CLI `--no-reuse`,
  API `?reuse=never`, web toggle.
- `kb.query` now honours `lecture_id`: **already-covered summaries no longer
  self-match the lecture currently being generated**.
- Per-run candidate dedup by `(source, qid)` — similar sections can no longer
  both claim the same PYQ. Deferred questions that survive the whole run are
  logged.
- Question re-ingest is idempotent per (exam, qid) — no more duplicates.
- Re-clustering rebuilds only pyq-sourced taxonomy and **relinks
  lecture/section associations by canonical name** instead of orphaning them.
- New `memory stats` CLI command + `kb_stats()` / KB-info API endpoint.

### LLM providers & infrastructure

- `shared/llm.py`: added **OpenAI and Gemini clients**; Anthropic completed
  (configurable `ANTHROPIC_MAX_TOKENS`, truncation now raises instead of
  yielding broken JSON); `get_llm_client` raises on unknown providers instead
  of silently falling back to Ollama; per-call `max_tokens`. Embeddings stay
  local via Ollama regardless of provider.
- Config unified: `cmkb/config.py` now re-exports `shared.config` (fixes the
  `gemma4:e4b` typo drift); `.env.example` and the web config page carry
  `LLM_PROVIDER` + API keys + the new model knobs; empty config fields no
  longer blank out `.env`.
- cmkb tagging/PageIndex traversal now route through the shared provider
  client; batched embeddings (`/api/embed`) instead of one HTTP call per
  topic; book-context results deduped across chunking + PageIndex retrieval.
- **PageIndex mode repaired**: relative imports, `PyPDF2`/`pyyaml` deps added,
  `OLLAMA_URL` → `OLLAMA_BASE`, correct `page_index_main` entry point, stored
  tree shape normalized on read; dead `models.py` / `continuation.py`
  deleted. Chunking ingest now tracks real page ranges per chunk.

### API & web

- **KB management page** (`/kb/manage`): inspect a KB (questions, exams,
  clusters, usage, chunks), add more question JSONs / reference PDFs,
  re-cluster, then continue to lecture upload. Reached after KB upload and
  after KB creation — the previously missing "add material to an existing KB"
  flow.
- Generation progress now streams via a **per-run log handler** (no more
  global `sys.stdout` monkeypatch; a lock prevents concurrent runs from
  interleaving).
- Blocking endpoints (`/extract`, KB ingest) no longer freeze the event loop;
  pasted JSON is validated server-side; upload filenames are sanitised;
  CORS is spec-valid; `/download/tex` no longer builds `None_output.tex`.
- Frontend: single `src/api.ts` client (`VITE_API_URL` override; API base was
  hardcoded in 7 files), `res.ok` checks everywhere (failures no longer
  render as success), fake rotating progress strings replaced with real
  per-step status, GeneratePage toggles updated to the new pipeline.

### Caching

- Cache files keyed by input filename + **content hash** + kb/lecture suffix
  + version — changed inputs or pipeline upgrades never serve stale results.
  Failures are never cached. `--fresh` ignores the cache for a run.
- Removed the extraction/generation cache split-brain (`run` now shares one
  cache); dead cache slots and methods removed.

### Docs

- `docs/pipeline.md` and `docs/PEDAGOGICAL_JSON_SCHEMA.md` rewritten for the
  new architecture; AI Guide chatbot prompts updated to the 2-step flow.
