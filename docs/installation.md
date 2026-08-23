# Installation Guide

This guide covers how to set up the ADHD Worksheets pipeline on your local machine.

## Prerequisites

- **Python 3.10+**
- **Ollama** installed locally (if you plan to use local models). Alternatively, you can use the Anthropic API.
- A LaTeX distribution (e.g., MacTeX, TeX Live) installed if you want to compile the resulting `.tex` files into PDFs yourself.

## 1. Setup the Python Environment

It is highly recommended to use a virtual environment to manage dependencies.

```bash
# Clone the repository (if applicable) and navigate to the directory
cd ADHD_Worksheets

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Mac/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install the required dependencies
pip install -r requirements.txt
```

## 2. Configure Environment Variables

The pipeline uses environment variables to route different tasks to specific LLMs, allowing you to use heavy models for complex reasoning (like generation) and faster, smaller models for filtering or tagging.

1. Copy the example configuration file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and configure your models. 
   
   If you are using **Ollama** locally, ensure `OLLAMA_BASE` points to your active server (default: `http://localhost:11434`), and that you have pulled the required models via `ollama pull <model_name>`.

   If you are using **Anthropic**, set `LLM_PROVIDER=anthropic` and provide your `ANTHROPIC_API_KEY`.

**Example `.env` configuration:**
```env
# General
LLM_PROVIDER=ollama
OLLAMA_BASE=http://localhost:11434
# ANTHROPIC_API_KEY=your_key_here

# --- Extraction pipeline ---
MODEL_EXTRACTION=gpt-oss:120b-cloud
MODEL_QUESTION_EXTRACT=gpt-oss:20b-cloud
MODEL_PEDAGOGY=gpt-oss:120b-cloud

# --- Generation pipeline ---
MODEL_THEORY=gpt-oss:120b-cloud
MODEL_QUESTIONS=gpt-oss:120b-cloud
MODEL_QUESTION_FILTER=gpt-oss:20b-cloud
MODEL_REVIEW=gpt-oss:20b-cloud
MODEL_CONTEXT_SUMMARY=gpt-oss:20b-cloud

# --- Memory module (cmkb) ---
EMBED_MODEL=nomic-embed-text
TAG_MODEL=gemma3n:e4b
PAGEINDEX_MODEL=gemma3n:e4b
```

## 3. Verify Installation

You can verify that the CLI is working correctly by checking the help menu:

```bash
python main_cli.py -h
```

You are now ready to start using the pipeline. See [usage.md](usage.md) for instructions on running the tools.
