# AI Learning Module Generator

An AI-powered pipeline that transforms lecture slides and supporting documents into structured, compilable LaTeX self-study modules with scaffolded theory, graded questions, and adapted past-year questions (PYQs).

## Features

- **PDF-to-Module pipeline** — feed in lecture slides, get a complete LaTeX learning module
- **Pedagogical structuring** — Bloom's taxonomy question ladder (recall → evaluate)
- **PYQ integration** — automatically extracts, maps, and adapts past exam questions
- **Deterministic compilation** — theory + questions assembled without LLM hallucination
- **Resumable** — all LLM outputs cached; interrupted runs resume automatically
- **Configurable** — objective mode (MCQs), review pass toggle, newpage control

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) running locally with your preferred models

### Setup

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Configure models
cp .env.example .env
# Edit .env with your model names
```

### Usage

```bash
# From a pre-extracted JSON (most common)
python main.py json/w5m1.json

# From a PDF slide (runs full extraction first)
python main.py pdfs/W5M1.pdf

# With options
python main.py json/w5m1.json --objective --no-review --no-newpage

# Custom support documents directory
python main.py json/w5m1.json --support-dir ./past_papers/
```

### CLI Flags

| Flag             | Default | Description                          |
|------------------|---------|--------------------------------------|
| `--objective`    | off     | Generate 4-option MCQs instead of open-ended questions |
| `--no-review`    | review on | Skip the QA review pass (saves tokens) |
| `--no-newpage`   | newpage on | Don't insert `\newpage` between questions |
| `--support-dir`  | `src/supporting/` | Custom path to PYQ/support documents |

## Project Structure

```
├── main.py                  # Unified entry point
├── .env                     # Model configuration (not committed)
├── .env.example             # Template for .env
├── requirements.txt         # Python dependencies
├── src/
│   ├── __init__.py
│   ├── prompts.py           # All LLM system prompts
│   ├── llm.py               # Ollama API wrapper
│   ├── cache.py             # Pipeline cache (resume support)
│   ├── formatter.py         # LaTeX formatting utilities
│   ├── sanitisation.py      # Unicode → LaTeX sanitisation
│   └── stages/
│       ├── __init__.py
│       ├── extraction.py    # Stage 1: PDF → JSON extraction
│       ├── pedagogy.py      # Stage 1.5: PYQ mapping + pedagogical metadata
│       └── sections.py      # Stage 2+3: per-section generation + formatting
├── json/                    # Pre-extracted JSON input files
├── pdfs/                    # Source PDF slides
├── output/                  # Generated .tex and context files
├── docs/
│   └── pipeline.md          # Detailed pipeline documentation
└── tests/                   # Test scripts
```

## Pipeline Overview

| Stage | Description | Type |
|-------|-------------|------|
| 1     | PDF parsing & content extraction | LLM |
| 1.5a  | PYQ extraction & section mapping | LLM |
| 1.5b  | Pedagogical structuring | LLM |
| 2.1   | Theory generation | LLM |
| 2.2   | Question generation (Bloom's ladder) | LLM |
| 2.3   | PYQ filter & adaptation | LLM |
| 2.4   | Section compile | Deterministic |
| 2.6   | Review pass (optional) | LLM |
| 2.5   | Context summarisation | LLM |
| 3     | Document formatting & assembly | Deterministic |

See [docs/pipeline.md](docs/pipeline.md) for detailed stage documentation.

## Configuration

Models are configured via `.env`:

```env
OLLAMA_API_URL=http://localhost:11434/api/generate
MODEL_PRO=gpt-oss:120b-cloud        # Heavy reasoning tasks
MODEL_FLASH=gpt-oss:20b-cloud       # Review and extraction
MODEL_FLASH_LITE=gpt-oss:20b-cloud  # Lightweight tasks
```

## Caching

All LLM outputs are cached in `.pipeline_cache/<filename>.cache.json`. If the pipeline is interrupted, it resumes from the last completed step. To force a fresh run:

```bash
rm -rf .pipeline_cache/
```
