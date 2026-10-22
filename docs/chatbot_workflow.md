# Using External Chatbots (Claude / ChatGPT / Gemini) for Extraction

You don't have to run the extraction pipeline locally. If you have access to a strong LLM chatbot (for example Claude, ChatGPT or Gemini) that accepts PDF uploads, you can use it to produce the pedagogical JSON (schema v2, see [PEDAGOGICAL_JSON_SCHEMA.md](PEDAGOGICAL_JSON_SCHEMA.md)) directly from your lecture PDF.

These are the same two prompts shown in the web app's **AI Guide** page (`/guide`, "Extract Lecture" tab). Once you have the final JSON, feed it to the `generate` command (or paste it into the web app's lecture upload page) to produce your LaTeX worksheet with memory integration.

## Workflow Overview

1. **Upload** your lecture PDF to the chatbot interface.
2. **Paste Prompt 1** to create the section map (with the raw content of each section).
3. **Paste Prompt 2** in the same chat to annotate every section (objectives, misconceptions, worked-example spec, embedded questions).
4. **Save** the final JSON array and run the `generate` CLI command (or paste it into the web app).

---

### Step 1: Upload and Create the Section Map

Upload your PDF to the chatbot. Copy and paste the following prompt:

```text
You are an academic extraction agent. You receive the text of a lecture deck (the attached PDF) and produce a section map for a self-study worksheet.

TASKS:
1. Clean the content: keep all academic text and formulas. Where a page is mostly a diagram or figure, describe what it shows based only on the surrounding text and captions — never invent visual details.
2. Segment the material into ordered sections by topic. Merge trivial follow-on slides into their parent section; keep genuinely distinct topics apart. Typically 3-8 sections.
3. For EACH section, populate "section_content" with the RAW teaching material of that section — definitions, formulas, descriptions — excluding material that belongs to other sections. Section content must be self-contained.

OUTPUT — a single JSON object:
{"section_map": [
  {"section_title": "...",
   "section_content": "...",
   "topics": ["..."],
   "subtopics": ["..."],
   "dependency_order": 1}
]}
Return valid JSON only in a code block so I can download it.
```

### Step 2: Annotate Each Section

Once the chatbot replies with the section map, paste the following prompt in the same chat:

```text
You are a curriculum designer. You do not write student-facing content. Using the section map you just produced, annotate EVERY section.

For each section, OUTPUT this JSON object (and repeat for all sections as a JSON array, in the same order):

{"section_title": "(copy exactly)",
 "learning_objectives": ["Student can ...", "..."],
 "key_misconceptions": ["...", "..."],
 "worked_example_spec": "...",
 "extracted_questions": [
   {"text": "...", "type": "numerical|conceptual|derivation|design|mcq",
    "difficulty": "recall|understand|apply|analyse|evaluate",
    "assumed_knowledge": ["..."]}
 ]}

RULES:
- 2-4 learning objectives, each achievable by a beginner reading only this section and the sections before it.
- 1-3 key misconceptions students commonly hold about this topic. Be specific.
- worked_example_spec: what a fully solved example should demonstrate. Empty string if purely conceptual.
- extracted_questions: every practice question or exercise embedded in that section's slides, verbatim. Do not paraphrase. Do not invent. Empty list if none.

The final output must be a JSON ARRAY — one object per section — each also containing the original fields (section_title, section_content, topics, subtopics, dependency_order) copied unchanged. Output ONLY valid JSON in a code block so I can download it.
```

The result is a JSON **array** with one object per section, containing both the Step 1 fields and the annotation fields — exactly the v2 schema the generator consumes. (The Step 1 output on its own, `{"section_map": [...]}`, is also accepted, but it has no objectives, misconceptions or embedded questions.)

---

### Step 3: Generate the Worksheet

1. Copy the final JSON output provided by the chatbot.
2. Save it to a file, for example, `chatbot_output.json`.
3. Use the `generate` command in the ADHD Worksheets CLI to compile the worksheet. This will automatically pull in relevant Past Year Questions and book context from your Knowledge Base (CMKB):

```bash
python main_cli.py generate chatbot_output.json \
    --kb course.cmkb \
    --lecture-id L01 \
    --out output/worksheet.tex
```

With `--kb`, this run writes to `course.cmkb` (section summaries + PYQ usage). Add `--no-memory-update` for a dry run, or work on a copy of the KB.

Alternatively, in the web app, paste the JSON into the text box on the **Upload Lecture** page instead of uploading a PDF.

That's it! The generation pipeline will now build your LaTeX worksheet (`.tex`) using the chatbot-authored pedagogy. Compile it to PDF yourself (for example with `pdflatex` or Overleaf).
