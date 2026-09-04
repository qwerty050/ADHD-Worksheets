# Pedagogical JSON Schema (v2)

This document defines the stable public contract for the Pedagogical JSON
consumed by the generation module to produce the final Typst worksheet. It is
produced by the extraction pipeline (`extract` / `run` commands, or the web
upload flow), or authored by an external tool (e.g. Claude, ChatGPT — see the
in-app AI Guide prompts).

## High-Level Structure

A **list of section objects**, one per worksheet section (theory + questions
are generated per section, in order).

```json
[
  {
    "section_title": "1. Introduction to Topic",
    "section_content": "Raw slide content or textbook text...",
    "topics": ["topic_1", "topic_2"],
    "subtopics": ["subtopic_1"],
    "dependency_order": 1,
    "learning_objectives": ["Student can define...", "Student can compute..."],
    "key_misconceptions": ["Confusing A with B", "Forgetting the scaling factor"],
    "worked_example_spec": "Show a 2x2 matrix projection with specific numbers.",
    "extracted_questions": [
      {
        "text": "What is the result of ...?",
        "type": "numerical",
        "difficulty": "apply",
        "assumed_knowledge": []
      }
    ]
  }
]
```

## Field Definitions

### Base content fields
- `section_title` *(string)*: Title of the section.
- `section_content` *(string)*: Raw teaching material (facts, formulas,
  descriptions) for this section. The Section Writer's primary input.
- `topics` *(list of strings)*: High-level topics (drive memory/PYQ retrieval).
- `subtopics` *(list of strings)*: More specific subtopics (also used for retrieval).
- `dependency_order` *(integer)*: Sequential ordering (re-assigned deterministically by the pipeline).

### Annotation fields
- `learning_objectives` *(list of strings)*: 2-4 statements beginning with "Student can...".
- `key_misconceptions` *(list of strings)*: 1-3 common mistakes students make.
- `worked_example_spec` *(string)*: What a fully solved worked example should
  demonstrate (dataset, procedure, takeaway). Empty string if the content is
  purely conceptual.
- `extracted_questions` *(list of objects)*: Questions embedded in the lecture
  slides for this section. Merged with memory-sourced PYQs as candidates for
  the Question Set Builder.
  - `text` *(string)*: Verbatim question text.
  - `type` *(string)*: `numerical`, `conceptual`, `derivation`, `design`, `mcq`.
  - `difficulty` *(string)*: `recall`, `understand`, `apply`, `analyse`, `evaluate`.
  - `assumed_knowledge` *(list of strings)*: Prerequisites needed to answer.

## Fields removed in v2 (and why)

| Field | Replacement |
|---|---|
| `teach_approach`, `opening_analogy`, `prerequisite_bridge` | The Section Writer's fixed skeleton (Motivation → Intuition → Formal Content → Worked Example → Key Takeaway) produces this structure directly. |
| `question_prompts` (5 Bloom seeds) | The Question Set Builder writes the ladder itself in one call, judged against the theory actually written. |
| `notation_introduced` | The Section Writer reports the notation it actually used — the notation table can never drift from the theory. |
| `worked_example_required` *(bool)* | Folded into `worked_example_spec` (non-empty string ⇒ example required). |
| `cleaned_content`, `prerequisite_gaps` (top level) | No longer produced; Stage-1 output is the section map only. |
| `mapped_sections`, `mapping_confidence`, `mapping_reason` | Questions are extracted per section, so they attach by construction. |

## Notes for external authoring

- The generation module also accepts the legacy dict envelope
  `{"section_map": [...]}`; a bare list is preferred.
- Unknown extra fields are ignored, but the fields above are what the pipeline
  actually consumes.
