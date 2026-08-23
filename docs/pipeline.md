# AI Learning Module Generation Pipeline

> Pedagogically structured pipeline that turns lecture slides into compilable LaTeX self-study modules with scaffolded theory, graded questions, and adapted memory-sourced extracted questions.

---

## Pipeline Overview

| Stage | Step | Type | Description |
|-------|------|------|-------------|
| **1** | Parsing / Extraction | LLM | Extract & organise lecture slide content into a structured JSON section map. |
| **1.5a** | Question Extraction | LLM | Extract practice questions embedded directly within the lecture slide. |
| **1.5b** | Pedagogical Structuring | LLM | Annotate each section with teaching metadata (analogies, objectives, etc.). |
| **2.1** | Theory Generation | LLM | Generate structured theory per section, optionally grounded by textbook context and shifted to a recap if already covered. |
| **2.2** | Question Generation | LLM | Scaffolded recall → evaluate question ladder based on the generated theory. |
| **2.3** | Extracted Qs Filter | LLM | Knowledge-check questions (both lecture-internal and PYQs from memory); include / adapt / defer. |
| **2.4** | Section Compile | **Deterministic** | Merge theory + questions into one LaTeX unit. |
| **2.5** | Context Summarisation | LLM | Update rolling context summary for the next section. |
| **2.6** | Review Pass *(opt)* | LLM | QA check for undefined terms and knowledge gaps. |
| **3** | Document Formatting | **Deterministic** | Notation tables + full LaTeX document assembly. |

---

## Data Flow

```
 ┌──────────────────────────────────────────────────────────────┐
 │  INPUT: PDF slide (Lecture)  OR  pre-extracted JSON          │
 └──────────────────────┬───────────────────────────────────────┘
                        │
           ┌── PDF? ────┼──── JSON? ──┐
           ▼                          │
  ┌─────────────────┐                 │
  │  Stage 1: Parse │                 │
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
  │ Stage 1.5a:      │         │ (section map       │
  │ Internal Q Extr  │         │  passed through)   │
  └────────┬─────────┘         └────────┬───────────┘
           │                            │
           ▼                            │
  ┌──────────────────┐                  │
  │ Stage 1.5b:      │◀────────────────┘
  │ Pedagogical      │
  │ Structuring      │
  └────────┬─────────┘
           │
           ▼  Pedagogical JSON
           │
    ┌──────┼──── for each section ──────────────┐
    │      ▼                                    │
    │  ┌───────────────────────────────────┐    │
    │  │ Memory Store (kb.query)           │    │
    │  │ (returns PYQs, book context,      │    │
    │  │  already_covered topics)          │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.1  Theory Generation            │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.2  Questions Generation         │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.3  Filter & Adapt PYQs + Qs     │    │
    │  │ (deferred → next section)         │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.4  Compile (deterministic)      │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.6  Review Pass (optional)       │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ 2.5  Context Summary              │    │
    │  └──────────┬────────────────────────┘    │
    │             ▼                             │
    │  ┌───────────────────────────────────┐    │
    │  │ Memory Store (kb.update)          │    │
    │  │ (Commits generated LaTeX to DB)   │    │
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
        └──────────────────┘
```

---

## Stage Details

### Stage 1 — Parsing / Extraction
**Input:** Lecture PDF Slide
**Output:** JSON Section Map
**What it does:** Extracts all academic text and formulas, identifies prerequisite gaps, segments content into ordered sections based on topics. Note: This stage no longer processes external support documents.

### Stage 1.5a — Question Extraction
**Input:** Target slide content
**Output:** Extracted questions (mapped to sections)
**What it does:** Extracts practice problems and worked examples embedded directly inside the lecture slide itself.

### Stage 1.5b — Pedagogical Structuring
**Input:** Stage 1 JSON + internal mapped questions
**Output:** Pedagogical JSON (schema contract)
**What it does:** Enriches each section with learning objectives, an opening analogy, misconception warnings, and a teach approach. Attaches the Stage 1.5a questions directly to the relevant sections.

### Stage 2.1 — Theory Generation
**Input:** Section raw content + pedagogical metadata + previous context + **book_context** + **already_covered**
**Output:** LaTeX formatted theory text
**What it does:** Generates structured theory. If `already_covered` is triggered from the memory store, it shifts the framing to a review rather than a fresh introduction.

### Stage 2.2 — Question Generation
**Input:** Section content + theory + question prompts + context
**Output:** 5-Level Bloom's Taxonomy questions
**What it does:** Produces a scaffolded question set expanding the metadata's question prompts from RECALL to EVALUATE.

### Stage 2.3 — Extracted Questions Filter & Adaptation
**Input:** Pre-mapped questions (**Internal Lecture Qs + Memory PYQs**) + context
**Output:** Adapted questions to include, and deferred questions
**What it does:** Performs a knowledge check on candidate questions against what has been covered so far. Adapts questions inline or defers them to a future section if prerequisites aren't met yet.

### Stage 2.4 & 3 — Compilation
**Input:** Theory text + generated questions + extracted questions
**Output:** Full LaTeX Document (`.tex`)
**What it does:** Deterministically builds the full document, handles pagination (`\newpage`), notation tables, and Unicode sanitization without any further LLM calls.

## Caching & Resumability

All LLM outputs are cached per-step in `.pipeline_cache/<filename>.cache.json`.
Crucially, when generation resumes from an interrupted state, it checks the cache for `memory_updated`. If the section was already committed to the Knowledge Base via `kb.update()`, it will strictly bypass the update step to prevent database duplication.
