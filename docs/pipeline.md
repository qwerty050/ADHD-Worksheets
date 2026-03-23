# AI Learning Module Generation Pipeline

> Pedagogically structured pipeline that turns lecture slides into compilable LaTeX self-study modules with scaffolded theory, graded questions, and adapted PYQs.

---

## Pipeline Overview

| Stage | Step | Type | Model | Description |
|-------|------|------|-------|-------------|
| **1** | Parsing / Extraction | LLM | `pro` | Extract & organise slide content into a structured JSON section map |
| **1.5a** | PYQ Extraction & Section Mapping | LLM | `flash` | Extract questions from support docs; map each to section(s) |
| **1.5b** | Pedagogical Structuring | LLM | `pro` | Annotate each section with teaching metadata |
| **2.1** | Theory Generation | LLM | `pro` | Generate structured theory per section |
| **2.2** | Question Generation | LLM | `pro` | Scaffolded recall → evaluate question ladder |
| **2.3** | PYQ Filter & Adaptation | LLM | `flashLite` | Knowledge-check PYQs; include / adapt / defer |
| **2.4** | Section Compile | **Deterministic** | — | Merge theory + questions into one LaTeX unit |
| **2.6** | Review Pass *(optional)* | LLM | `flash` | QA check for undefined terms, knowledge gaps |
| **2.5** | Context Summarisation | LLM | `flashLite` | Update rolling context summary |
| **3** | Document Formatting | **Deterministic** | — | Notation tables + full LaTeX assembly |

---

## Data Flow

```
 ┌──────────────────────────────────────────────────────────────┐
 │  INPUT: PDF slide  OR  pre-extracted JSON                    │
 └──────────────────────┬───────────────────────────────────────┘
                        │
           ┌── PDF? ────┼──── JSON? ──┐
           ▼                          │
  ┌─────────────────┐                 │
  │  Stage 1: Parse │ (LLM — pro)    │
  │  & Extract      │                 │
  └────────┬────────┘                 │
           │                          │
           ▼                          ▼
           ┌──────────────────────────┐
           │  Extraction JSON         │
           │  (section map + content) │
           └────────────┬─────────────┘
                        │
           ┌────────────┼────────────────┐
           ▼                             ▼
  ┌──────────────────┐         ┌────────────────────┐
  │ Stage 1.5a: PYQ  │         │ (section map       │
  │ Extract + Map    │         │  passed through)   │
  └────────┬─────────┘         └────────┬───────────┘
           │                            │
           ▼                            │
  ┌──────────────────┐                  │
  │ Stage 1.5b:      │◀────────────────┘
  │ Pedagogical      │
  │ Structuring      │
  └────────┬─────────┘
           │
           ▼  enriched section map
           │
    ┌──────┼──── for each section ──────────────┐
    │      ▼                                    │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.1  Theory (pro)                │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.2  Questions (pro)  → JSON     │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.3  PYQs (flashLite) → JSON     │    │
    │  │ deferred → next section          │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.4  Compile (deterministic)     │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.6  Review Pass (optional)      │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.5  Context Summary             │    │
    │  └──────────┬────────────────────────┘    │
    └─────────────┼─────────────────────────────┘
                  │
                  ▼
       ┌───────────────────────┐
       │  Stage 3: Format      │  (Deterministic)
       │  • Notation tables    │
       │  • LaTeX assembly     │
       └───────────┬───────────┘
                   │
                   ▼
        ┌──────────────────┐
        │  output/*.tex    │
        │  output/*.txt    │
        └──────────────────┘
```

---

## Stage Details

### Stage 1 — Parsing / Extraction

> **File:** `src/stages/extraction.py`
> **Type:** LLM call · **Model:** `pro` · **Output:** JSON

**Input:** PDF slide + supporting docs + optional context files

**Output:**
```json
{
  "cleaned_content": "...",
  "prerequisite_gaps": ["..."],
  "section_map": [
    {
      "section_title": "...",
      "section_content": "...",
      "topics": ["..."],
      "subtopics": ["..."],
      "dependency_order": 1
    }
  ],
  "extracted_pyqs": []
}
```

**What it does:** Reads the target slide (PDF), extracts all academic text and formulas, identifies prerequisite gaps, segments content into ordered sections, and isolates raw content for each section.

---

### Stage 1.5a — PYQ Extraction & Section Mapping

> **File:** `src/stages/pedagogy.py`
> **Type:** LLM call · **Model:** `flash` · **Output:** JSON

**Input:** Support documents (past papers, textbooks) + section map from Stage 1

**Output:**
```json
{
  "extracted_pyqs": [
    {
      "text": "...",
      "source": "...",
      "type": "numerical",
      "difficulty": "apply",
      "assumed_knowledge": ["..."],
      "mapped_sections": ["3. Algorithm Steps"],
      "mapping_confidence": "high",
      "mapping_reason": "..."
    }
  ]
}
```

**What it does:** Extracts every question from support documents and maps each to the relevant section(s) from the section map.

---

### Stage 1.5b — Pedagogical Structuring

> **File:** `src/stages/pedagogy.py`
> **Type:** LLM call · **Model:** `pro` · **Output:** JSON

**Input:** Stage 1 JSON + mapped PYQs from Stage 1.5a

**Output:** Enriched section map — each section annotated with:
- `learning_objectives` — 2-4 "Student can..." statements
- `teach_approach` — one of: analogy_first, example_first, concept_first, problem_first
- `opening_analogy` — everyday-life analogy (or null)
- `prerequisite_bridge` — needed/covers/because
- `key_misconceptions` — 1-3 common mistakes
- `notation_introduced` — `[{symbol, meaning}]`
- `worked_example_required` + `worked_example_spec`
- `question_prompts` — seeds at 5 Bloom levels (recall → evaluate)

---

### Stage 2.1 — Theory Generation

> **File:** `src/stages/sections.py`
> **Type:** LLM call · **Model:** `pro` · **Output:** LaTeX

**Input:** Section raw content + pedagogical metadata + previous context

**Output:** Structured LaTeX theory following this exact order:
1. Prerequisite Bridge (if needed)
2. Motivation (using teach_approach + opening_analogy)
3. Intuition (plain English, no formulas)
4. Formal Definition (notation + preempt misconceptions)
5. Worked Example (if required)
6. Key Takeaway

---

### Stage 2.2 — Question Generation

> **File:** `src/stages/sections.py`
> **Type:** LLM call · **Model:** `pro` · **Output:** JSON

**Input:** Section raw content + theory + question prompts + previous context + objective mode flag

**Output:**
```json
{
  "questions": [
    "% --- RECALL ---\n\\textbf{Q1.} Define ...",
    "% --- UNDERSTAND ---\n\\textbf{Q2.} Explain ...",
    "..."
  ]
}
```

**What it does:** Produces a scaffolded question set expanding the metadata's question prompts across 5 Bloom levels: RECALL (1-2) → UNDERSTAND (2) → APPLY (2-3) → ANALYSE (1-2) → EVALUATE (1).

---

### Stage 2.3 — PYQ Filter & Adaptation

> **File:** `src/stages/sections.py`
> **Type:** LLM call · **Model:** `flashLite` · **Output:** JSON

**Input:** Section raw content + pre-mapped PYQs + deferred PYQs + previous context

**Output:**
```json
{
  "questions": ["LaTeX question 1", "LaTeX question 2"],
  "deferred_pyqs": [{"text": "...", "assumed_knowledge": ["..."]}]
}
```

**What it does:** For each PYQ mapped to this section, performs a knowledge check (INCLUDE / ADAPT / DEFER), adapts questions that need it, and defers questions whose prerequisites haven't been covered yet.

---

### Stage 2.4 — Section Compile (Deterministic)

> **File:** `src/formatter.py` → `compile_section()`
> **Type:** Pure Python — no LLM call

**Input:** Section title + theory text + HOTS questions list + PYQ questions list + newpage flag

**Output (newpage=True):**
```latex
\section{Title}
[Theory]
\newpage
\subsection*{Questions}
Q1
\newpage
Q2
\newpage
Q3
```

**Output (newpage=False):**
```latex
\section{Title}
[Theory]
\newpage
\subsection*{Questions}
Q1
Q2
Q3
```

---

### Stage 2.6 — Review Pass (Optional)

> **File:** `src/stages/sections.py`
> **Type:** LLM call · **Model:** `flash` · **Output:** JSON

**Input:** Compiled section LaTeX + pedagogical metadata + previous context

**Output:**
```json
{
  "section_title": "...",
  "status": "pass" | "flag",
  "flags": [
    {"type": "undefined_term", "term": "...", "suggestion": "..."}
  ],
  "summary": "..."
}
```

**Flag types:** `undefined_term`, `knowledge_assumption`, `missing_motivation`, `learning_objective_gap`, `ladder_gap`

Disable with `--no-review` to save tokens.

---

### Stage 2.5 — Context Summarisation

> **File:** `src/stages/sections.py`
> **Type:** LLM call · **Model:** `flashLite` · **Output:** plain text

**Input:** Current rolling context + newly added section info

**Output:** Concise summary (max 300 words) of what the student has learned so far.

---

### Stage 3 — Document Formatting (Deterministic)

> **File:** `src/formatter.py`
> **Type:** Pure Python — no LLM call

**Input:** All compiled sections + section titles + notation data

**Output:** Complete `.tex` document with:
- LaTeX preamble with all required packages
- Title page + table of contents
- Per-section notation tables
- Assembled sections with `\newpage` separators
- Unicode sanitisation via `src/sanitisation.py`

---

## Caching

All LLM outputs are cached per-step in `.pipeline_cache/<filename>.cache.json`.

**Cache keys:**
- `extraction` — Stage 1 output
- `pyq_extraction` — Stage 1.5a output
- `pedagogical` — Stage 1.5b enriched section map
- Per-section: `theory`, `hots`, `pyq`, `deferred_pyqs`, `compiled`, `review`, `context`

If the pipeline is interrupted, it resumes from the last completed step automatically. Delete the cache file to force a fresh run:

```bash
rm -rf .pipeline_cache/
```
