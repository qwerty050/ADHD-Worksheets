# Pedagogical JSON Schema

This document defines the stable public contract for the Pedagogical JSON format used in the `ADHD Worksheets` generator.

The generation module (Stage 2) consumes this JSON to produce the final LaTeX worksheet. This JSON can be generated using the built-in extraction pipeline (Stage 1), or authored by an external tool (e.g. Claude, ChatGPT).

## High-Level Structure

The JSON is a list of Section Objects. Each Section Object represents one cohesive topic block that will be compiled into a LaTeX section.

```json
[
  {
    "section_title": "1. Introduction to Topic",
    "section_content": "Raw slide content or textbook text...",
    "topics": ["topic_1", "topic_2"],
    "subtopics": ["subtopic_1"],
    "dependency_order": 1,
    "learning_objectives": ["Student can define...", "Student can compute..."],
    "teach_approach": "example_first",
    "opening_analogy": "Think of this like sorting mail...",
    "prerequisite_bridge": {
      "needed": true,
      "covers": "Basic matrix multiplication",
      "because": "Without this, the projection step will seem like magic."
    },
    "key_misconceptions": ["Confusing A with B", "Forgetting the scaling factor"],
    "notation_introduced": [
      {
        "symbol": "\\hat{y}",
        "meaning": "predicted value"
      }
    ],
    "worked_example_required": true,
    "worked_example_spec": "Show a 2x2 matrix projection with specific numbers.",
    "question_prompts": {
      "recall": "Define the core equation...",
      "understand": "Explain why the scalar matters...",
      "apply": "Given matrix X, compute...",
      "analyse": "What happens if we remove the scalar?",
      "evaluate": "Design a projection matrix for..."
    },
    "extracted_questions": [
      {
        "text": "What is the result of ...?",
        "source": "lecture slide",
        "type": "numerical",
        "difficulty": "apply",
        "assumed_knowledge": [],
        "mapped_sections": ["1. Introduction to Topic"],
        "mapping_confidence": "high",
        "mapping_reason": "Direct application of the formula."
      }
    ]
  }
]
```

## Field Definitions

### Base Content Fields
- `section_title` *(string)*: The title of the section.
- `section_content` *(string)*: The raw textual content representing the facts, formulas, and text for this section.
- `topics` *(list of strings)*: High-level knowledge topics this section covers (used for memory retrieval).
- `subtopics` *(list of strings)*: More specific subtopics.
- `dependency_order` *(integer)*: Sequential ordering.

### Pedagogical Metadata
- `learning_objectives` *(list of strings)*: 2-4 statements beginning with "Student can...".
- `teach_approach` *(string)*: Must be one of `analogy_first`, `example_first`, `concept_first`, `problem_first`.
- `opening_analogy` *(string | null)*: An everyday-life analogy to introduce the concept.
- `prerequisite_bridge` *(object)*:
  - `needed` *(boolean)*: True if a brief recap of a prerequisite is required.
  - `covers` *(string)*: The concept to be recapped.
  - `because` *(string)*: Justification for why it's needed.
- `key_misconceptions` *(list of strings)*: 1-3 common mistakes students make.
- `notation_introduced` *(list of objects)*:
  - `symbol` *(string)*: The LaTeX symbol (e.g. `\theta`).
  - `meaning` *(string)*: Plain English meaning.
- `worked_example_required` *(boolean)*: True if the LLM should generate a full step-by-step example.
- `worked_example_spec` *(string)*: If required, what the example should look like.

### Questions
- `question_prompts` *(object)*: Seeds for generating original questions at all 5 Bloom levels:
  - `recall` *(string)*
  - `understand` *(string)*
  - `apply` *(string)*
  - `analyse` *(string)*
  - `evaluate` *(string)*
- `extracted_questions` *(list of objects)*: Actual questions extracted from the lecture slides that are mapped to this section. They will be merged with memory-sourced past paper questions during generation.
  - `text` *(string)*: The verbatim question text.
  - `source` *(string)*: e.g., "lecture slide".
  - `type` *(string)*: `numerical`, `conceptual`, `derivation`, `design`, `mcq`.
  - `difficulty` *(string)*: `recall`, `understand`, `apply`, `analyse`, `evaluate`.
  - `assumed_knowledge` *(list of strings)*: Prerequisites to answer the question.
  - `mapped_sections` *(list of strings)*: Should include `section_title`.
  - `mapping_confidence` *(string)*: `high`, `medium`, `low`.
  - `mapping_reason` *(string)*: Why it maps here.
