# Using External Chatbots (Claude / ChatGPT / Gemini) for Extraction

You don't have to run the extraction pipeline locally. If you have access to powerful web-based LLMs like **Claude 3.5 Sonnet**, **ChatGPT (GPT-4o)**, or **Gemini 1.5 Pro**, you can use them to extract the pedagogical JSON directly from your lecture PDFs. 

Once you get the final JSON from the chatbot, you can feed it directly into the `generate` command of this pipeline to produce your Typst worksheets with memory integration.

## Workflow Overview

1. **Upload** your lecture PDF to the chatbot interface.
2. **Paste Prompt 1** to extract the raw content and create the section map.
3. **Paste Prompt 2** to extract any embedded questions.
4. **Paste Prompt 3** to add the pedagogical metadata.
5. **Download** the final JSON and run the `generate` CLI command.

---

### Step 1: Upload and Extract (Stage 1)

Upload your PDF to the chatbot. Copy and paste the following prompt:

```text
You are an academic extraction agent. Your task is to clean and organize content from the attached lecture slide, generate a Section Map, and isolate the raw content for each section.

TASKS:
1. Clean Slide Content: Extract all academic text, formulas, and describe diagrams from the Target Slide. Organize it logically.
2. Context Gap Analysis: Identify if any concepts in the slide require prerequisites NOT found in the provided "Previous Context".
3. Section Map Generation: Segment the extracted content into ordered sections based on topics and subtopics.
4. Per-Section Content Isolation: For EACH section in the map, extract and populate its `section_content` field with the RAW content relevant to that section — including definitions, formulas, diagram descriptions, and slide references. Each section's content must be self-contained and exclude material belonging to other sections.

Return your findings in valid JSON format responding to this structure:
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
  ]
}
```

### Step 2: Extract Embedded Questions (Stage 1.5a)

Once the chatbot replies with the first JSON, paste the following prompt to extract questions:

```text
You are a question extraction and classification agent. 
Using the JSON you just generated, perform the following two tasks:

TASK 1 — EXTRACTION:
Extract every practice question, worked example problem, or exercise embedded in the lecture slide itself.
For each question record:
  - "text": the full question text, verbatim
  - "source": "lecture slide"
  - "type": one of [numerical, conceptual, derivation, design, mcq]
  - "difficulty": one of [recall, understand, apply, analyse, evaluate]
  - "assumed_knowledge": list any concepts the question assumes the student already knows

TASK 2 — SECTION MAPPING:
For each extracted question, identify which section(s) from the section map it belongs to.
Assign:
  - "mapped_sections": list of section_title strings from the section map that this question is relevant to
  - "mapping_confidence": one of [high, medium, low]
  - "mapping_reason": one sentence explaining why

RULES:
- Do not paraphrase or modify questions during extraction. Preserve original wording exactly.
- If a question cannot be mapped to any section with confidence, set mapped_sections to [] and mapping_confidence to "low". Do not discard it.
- Do not invent questions. Extract only what is present in the slide.

OUTPUT FORMAT:
{
  "extracted_questions": [
    {
      "text": "...",
      "source": "lecture slide",
      "type": "...",
      "difficulty": "...",
      "assumed_knowledge": ["..."],
      "mapped_sections": ["..."],
      "mapping_confidence": "...",
      "mapping_reason": "..."
    }
  ]
}

Return valid JSON only.
```

### Step 3: Pedagogical Structuring (Stage 1.5b)

Finally, paste the following prompt to structure the JSON for our generation pipeline:

```text
You are a curriculum designer. Your job is to read the extracted section map and the extracted questions, and annotate each section with pedagogical metadata.

FOR EACH SECTION, DETERMINE AND OUTPUT:

"learning_objectives": [2-4 statements in the form "Student can..."]
"teach_approach": Choose ONE: analogy_first | example_first | concept_first | problem_first
"opening_analogy": One concrete everyday-life analogy (no math/domain examples).
"prerequisite_bridge": {
  "needed": true/false,
  "covers": "...",
  "because": "..."
}
"key_misconceptions": [1-3 things students commonly get wrong about this topic.]
"notation_introduced": [ {"symbol": "...", "meaning": "..."} ]
"worked_example_required": true/false
"worked_example_spec": "If required: describe exactly what the example should show"
"question_prompts": {
  "recall":      "...",
  "understand":  "...",
  "apply":       "...",
  "analyse":     "...",
  "evaluate":    "..."
}
"extracted_questions": [Transfer any questions from the extracted_questions list that have THIS section's title in their "mapped_sections" list.]

CONSTRAINTS:
- Assume the student knows ONLY what appears in sections before this one.
- The opening_analogy must use everyday life, not domain examples.
- Every section must have question prompts at all five levels.
- prerequisite_bridge.needed should be true liberally.

OUTPUT: Return the full, finalized JSON object. It must have the `section_map` array where each section object now includes all of these new fields. Output ONLY valid JSON in a code block so I can download it.
```

---

### Step 4: Generate the Worksheet

1. Copy the final JSON output provided by the chatbot.
2. Save it to a file, for example, `chatbot_output.json`.
3. Use the `generate` command in the ADHD Worksheets CLI to compile the worksheet. This will automatically pull in relevant Past Year Questions and book context from your Knowledge Base (CMKB):

```bash
python main_cli.py generate chatbot_output.json \
    --kb course.cmkb \
    --lecture-id L01 \
    --out output/worksheet.typ
```

That's it! The generation pipeline will now build your Typst worksheet perfectly using the chatbot-authored pedagogy.
