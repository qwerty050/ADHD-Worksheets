# Usage Guide

The ADHD Worksheets generator is operated entirely via a central Command Line Interface (CLI): `main_cli.py`.

The CLI provides commands for both the generation pipeline (Extract -> Generate) and managing the underlying Course Memory Knowledge Base (CMKB).

## End-to-End Generation

The easiest way to generate a worksheet is to use the `run` command, which automatically handles PDF extraction and subsequent LaTeX generation.

```bash
python main_cli.py run path/to/lecture.pdf \
    --kb course.cmkb \
    --lecture-id L01 \
    --out output/worksheet.tex
```

**Options for `run` and `generate`:**
- `--no-memory-update`: Generates the worksheet but skips committing the results back into the memory store. Useful for dry runs.
- `--objective`: Converts the generated questions (Recall -> Evaluate) into 4-option Multiple Choice Questions (MCQs).
- `--no-review`: Skips the final LLM-based QA pass to save tokens/time.
- `--no-newpage`: Prevents the compiler from adding a `\newpage` between every single generated question.

---

## Step-by-Step Generation

If you want to manually inspect or edit the pedagogical structure before generating the final worksheet, you can split the process into two steps.

### Step 1: Extraction
Extracts content, internal questions, and generates pedagogical metadata from a lecture PDF. This does not require the memory module.

```bash
python main_cli.py extract path/to/lecture.pdf --out output/pedagogy.json
```

*You can now open `output/pedagogy.json` and manually adjust learning objectives, analogies, or section titles before compiling.*

*Tip: You can also use powerful external LLMs (like Claude or ChatGPT) to perform this extraction manually using our pre-written prompts. See the [Chatbot Extraction Workflow](chatbot_workflow.md) for details.*

### Step 2: Generation
Takes the (potentially hand-edited) pedagogical JSON, queries the memory store for PYQs and book context, and generates the LaTeX worksheet.

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

### 3. Ingest Past Year Questions (PYQs)
Add a JSON file containing past exam questions.
```bash
python main_cli.py memory ingest questions course.cmkb exams.json
```

*Tip: You can rapidly digitize raw past paper PDFs into the exact JSON format required here by using web chatbots. See the [PYQ Chatbot Workflow](pyq_chatbot_workflow.md) for the pre-written prompt.*

### 4. Cluster Topics
After ingesting materials, cluster the underlying topics to build the lexical and semantic retrieval index.
```bash
python main_cli.py memory cluster course.cmkb
```

### 5. Inspect the Database
View the topics currently held in memory to ensure your lecture slides will match against them.
```bash
python main_cli.py memory inspect course.cmkb
```
