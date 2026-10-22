# Usage Guide

The ADHD Worksheets generator can be operated using either the **Web App (UI)** or the **Command Line Interface (CLI)**.

## Web App (UI)
The easiest way to use the pipeline is via the included React + FastAPI web application, which provides a full GUI for creating knowledge bases, uploading lectures, and generating worksheets.

1. Start the FastAPI backend from the repo root: `uvicorn api.server:app --reload --port 8000`
2. Start the React frontend: `cd web && npm install && npm run dev` (`npm install` is only needed the first time)
3. Open `http://localhost:5173` in your browser.

The web app works on a copy: an uploaded or newly created knowledge base lives in a temporary session folder on the server, and memory updates are written to that copy. Download the updated KB from the final page if you want to keep them. Sessions are held in memory and are lost when the backend restarts (`--reload` restarts it whenever a `.py` file changes).

---

## Command Line Interface (CLI)

For automation or terminal enthusiasts, you can use the central CLI: `main_cli.py`.
The CLI provides commands for both the generation pipeline (Extract -> Generate) and managing the underlying Course Memory Knowledge Base (CMKB).

## End-to-End Generation

The easiest way to generate a worksheet is to use the `run` command, which automatically handles PDF extraction and subsequent LaTeX generation.

```bash
python main_cli.py run path/to/lecture.pdf \
    --kb course.cmkb \
    --lecture-id L01 \
    --out output/worksheet.tex
```

`run` also writes the extracted pedagogical JSON next to the worksheet (here `output/worksheet.json`).

**Options for `run` and `generate`:**
- `--out` (required): Output `.tex` path.
- `--kb`: Path to the `.cmkb` knowledge base. Optional; without it, no PYQs, book context or memory are used.
- `--lecture-id`: Lecture ID recorded with the memory update and used to exclude this lecture's own sections from "already covered". Set it whenever you pass `--kb`.
- `--no-memory-update`: Generates the worksheet but skips committing the results back into the memory store. Useful for dry runs.
- `--objective`: Converts the generated questions (Recall -> Evaluate) into 4-option Multiple Choice Questions (MCQs).
- `--no-newpage`: Prevents the compiler from adding a `\newpage` between every single generated question.
- `--no-reuse`: Never serve PYQs that a previous worksheet already used (default: prefer unused ones, fall back to used ones when a topic runs dry).
- `--fresh`: Ignore any cached progress in `.pipeline_cache/` for this run.

**Note:** with `--kb`, `run` and `generate` write to that `.cmkb` file in place (section summaries and PYQ usage). Use `--no-memory-update` or a copy of the KB for experiments.

---

## Step-by-Step Generation

If you want to manually inspect or edit the pedagogical structure before generating the final worksheet, you can split the process into two steps.

### Step 1: Extraction
Extracts content, internal questions, and generates pedagogical metadata from a lecture PDF. This does not require the memory module.

```bash
python main_cli.py extract path/to/lecture.pdf --out output/pedagogy.json
```

*You can now open `output/pedagogy.json` and manually adjust learning objectives, misconceptions, embedded questions, or section titles before compiling. The format is described in [PEDAGOGICAL_JSON_SCHEMA.md](PEDAGOGICAL_JSON_SCHEMA.md).*

*Tip: You can also use a strong LLM chatbot (like Claude or ChatGPT) to perform this extraction manually using our pre-written prompts. See the [Chatbot Extraction Workflow](chatbot_workflow.md) for details.*

### Step 2: Generation
Takes the (potentially hand-edited) pedagogical JSON, queries the memory store for PYQs and book context, and generates the LaTeX worksheet. `generate` accepts the same options as `run`.

```bash
python main_cli.py generate output/pedagogy.json \
    --kb course.cmkb \
    --lecture-id L01 \
    --out output/worksheet.tex
```

---

## Managing the Course Memory (CMKB)

The `memory` command acts as a passthrough to the CMKB tool, allowing you to build and inspect the knowledge base that grounds your worksheets.

### 1. Create a new Knowledge Base
```bash
python main_cli.py memory create course.cmkb --name "Machine Learning"
```

### 2. Ingest Reference Material
Add textbook chapters or reference PDFs. The memory module will chunk or page-index the document.
```bash
python main_cli.py memory ingest pdf course.cmkb textbook.pdf --mode chunking
```
`--mode` is `chunking` or `page_index`; if omitted, the KB's `--pdf-mode` from `memory create` is used (default `chunking`).

*Known issue: `page_index` ingestion currently fails with a `NameError` (`cmkb/ingest_pdf.py`), from the CLI and from the web app's "Detailed indexing (PageIndex)" option. Use `chunking`.*

### 3. Ingest Past Year Questions (PYQs)
Add a JSON file containing past exam questions.
```bash
python main_cli.py memory ingest questions course.cmkb exams.json
```

*Tip: You can rapidly digitize raw past paper PDFs into the exact JSON format required here by using web chatbots. See the [PYQ Chatbot Workflow](pyq_chatbot_workflow.md) for the pre-written prompt.*

### 4. Cluster Topics
After ingesting questions, cluster their topic tags into the canonical topic taxonomy (plus LLM-generated aliases, using `TAG_MODEL`) that retrieval matches lecture topics against. Re-run it after adding more questions.
```bash
python main_cli.py memory cluster course.cmkb
```

### 5. Inspect the Database
View the topics currently held in memory to ensure your lecture slides will match against them.
```bash
python main_cli.py memory inspect course.cmkb
```
(`inspect` accepts `--lecture-id` but currently ignores it.)

### Other `memory` subcommands

| Command | What it does |
|---|---|
| `memory create <kb> --name NAME [--pdf-mode chunking\|page_index] [--embed-model nomic-embed-text] [--embed-dim 768]` | Create a KB. `--embed-model` defaults to `nomic-embed-text` (not `EMBED_MODEL`); keep it equal to `EMBED_MODEL`. |
| `memory query <kb> --topics "a, b" [--lecture-id L01] [-k 8] [--no-reuse]` | Print the retrieval result (PYQs, book context, already-covered summaries) as JSON. |
| `memory debug-topic <kb> "query"` | Show lexical and nearest-embedding topic matches for a string. |
| `memory ingest lecture <kb> <lecture.json> --lecture-id L01` | Register a lecture's topics against the taxonomy. Expects the `{"section_map": [...]}` envelope; the bare list written by `extract` currently fails. |
| `memory ingest section <kb> --section-json F --summary F --latex F --lecture-id L01 --topics "a, b"` | Manually commit a section (the files hold the section JSON, summary text and LaTeX). |
| `memory stats` | KB overview counts. *Known issue: currently unusable (the subcommand takes no KB path).* |

Run `python main_cli.py memory <command> -h` for the full argument list.

---

## HTTP API

`api/server.py` (FastAPI) backs the web app; all routes are under `/api`. The web client (`web/src/api.ts`) uses all of them.

| Route | Purpose |
|---|---|
| `GET /api/config` | Return the values in `.env` (creates `.env` from `.env.example` if missing). |
| `POST /api/config` | Write the given keys to `.env` (empty values are skipped). Restart the server to apply. |
| `POST /api/sessions` | Create a session (temporary working folder); returns `session_id`. |
| `POST /api/sessions/{id}/kb/upload` | Upload an existing `.cmkb` (multipart `file`). |
| `POST /api/sessions/{id}/kb/create` | Create a new KB (form field `name`). |
| `GET /api/sessions/{id}/kb` | KB overview counts. |
| `POST /api/sessions/{id}/kb/ingest_questions` | Ingest question JSON files (multipart `files`). |
| `POST /api/sessions/{id}/kb/ingest_pdf` | Ingest reference PDFs (multipart `files`, form `mode`, default `chunking`). |
| `POST /api/sessions/{id}/kb/cluster` | Rebuild the topic taxonomy. |
| `POST /api/sessions/{id}/extract` | Set the lecture: form `lecture_id` plus one of `json_file`, `json_text` or `pdf_file` (checked in that order; a PDF runs the extraction pipeline). |
| `GET /api/sessions/{id}/generate` | Run generation and stream progress as Server-Sent Events. Query: `objective`, `newpage_per_question`, `update_memory`, `reuse=prefer\|never`. Log lines arrive as events, failures as `ERROR: ...`, and the stream ends with `None`. Returns 409 if another generation is running. |
| `GET /api/sessions/{id}/download/{tex\|cmkb}` | Download the worksheet or the session's KB. |
| `DELETE /api/sessions/{id}` | Delete the session and its folder. |
