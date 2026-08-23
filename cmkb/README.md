# Course Memory Knowledge Base (CMKB) Integration Guide

The `cmkb` package serves as the memory subsystem for the academic worksheet-generation pipeline. Its purpose is to track all knowledge associated with a course: practice questions (PYQs), textbook references, extracted lecture data, and **what has already been generated** in previous worksheets. 

This document explains how to integrate the programmatic `KnowledgeBase` API directly into your generation module.

## 1. Setup & Initialization

### Environment Variables
Ensure a `.env` file exists at the root of your working directory where the process is launched. It must specify the Ollama connection and the models to use:

```env
OLLAMA_BASE=http://localhost:11434
EMBED_MODEL=nomic-embed-text
TAG_MODEL=gemma3n:e4b
PAGEINDEX_MODEL=gemma4:e4b
```

### Loading the Knowledge Base
Inside your generation pipeline, initialize the `KnowledgeBase` instance using the single-file `.cmkb` database.

```python
from cmkb import KnowledgeBase

# If the file doesn't exist, create it first:
# kb = KnowledgeBase.create("course_data.cmkb", name="Machine Learning")

# To load an existing KB:
kb = KnowledgeBase.load("course_data.cmkb")
```

---

## 2. The Ingestion Pipeline

Before generating worksheets, the KB needs to be populated with source material. This is usually done once per course or lecture. 

### Ingesting Practice Questions (PYQs)
```python
kb.ingest_questions("path/to/exams.json")
# After ingesting all questions, run the cluster algorithm to build the canonical topic taxonomy:
kb.cluster() 
```

### Ingesting Reference Material (PDFs)
```python
# Standard chunking approach
kb.ingest_pdf("path/to/textbook.pdf", mode="chunking")

# Advanced LLM-driven PageIndex tree approach (requires PageIndex dependencies)
kb.ingest_pdf("path/to/textbook.pdf", mode="page_index")
```

### Ingesting Lecture Data
When a new lecture occurs, feed the extracted lecture JSON into the KB to register its topics against the taxonomy. Unmatched topics are automatically added as new canonical concepts.
```python
kb.ingest_lecture("path/to/extracted_lecture.json", lecture_id="L01")
```

---

## 3. The Generation Loop (Core Integration)

When your pipeline decides to generate a new worksheet section covering a specific set of topics, it interacts with the KB in a strict **two-step process**: **Query** (before writing) and **Update** (after writing).

### Step 3a: Query the KB (Before Generating)

Call `kb.query()` with the intended topics to retrieve context and check for overlap.

```python
topics_to_cover = ["Support Vector Machines", "Kernel Trick"]

context = kb.query(topics=topics_to_cover, lecture_id="L01", k=5)
```

The returned `context` dictionary contains three crucial lists:
1. **`questions`**: All canonical questions matching the topics exactly. Use these as practice problems in the worksheet.
2. **`book_context`**: Reference snippets from the textbook PDFs to ground the LLM's explanations.
3. **`already_covered`**: **CRITICAL**. This lists any previously generated worksheet sections that share a high semantic similarity with these topics. If this list is **not empty**, your generation module should alter its behavior (e.g., skip the topic, or write a "Review" section instead of an "Introduction").

### Step 3b: Update the KB (After Generating)

Once your generation module successfully creates the LaTeX for the section and summarizes it, you **must** feed this back into the KB. This closes the memory loop.

```python
latex_output = "\\section{SVMs} Support vector machines are..."
summary_of_section = "Introduced SVMs, explaining maximal margins and the kernel trick."
section_source_json = {"metadata": "passed to generation module"}

new_section_id = kb.update(
    lecture_id="L01",
    section_json=section_source_json,
    summary=summary_of_section,
    latex=latex_output,
    topics=topics_to_cover
)
```

This `update` call accomplishes several things:
1. Links the generated LaTeX to the requested topics.
2. Embeds the `summary` into the `summaries` FAISS index. 
3. Ensures that future `kb.query()` calls for "Kernel Trick" will populate the `already_covered` list with this exact summary, preventing duplicate worksheet content!

## FAQ

**Q: Can I use the CLI instead of Python code?**
Yes. Every python method has a 1:1 mapping in the `cmkb_cli.py` wrapper, which is useful for debugging, inspecting the state of the KB, or doing bulk background ingestions via bash scripts.

**Q: Does it use an LLM during the query phase?**
No, unless the PDF was ingested using `page_index` mode. `chunking` mode and Question retrieval use pure vector similarity (FAISS) and lexical matching, making them extremely fast and deterministic.
