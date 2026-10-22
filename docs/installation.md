# Installation Guide

This guide covers how to set up the ADHD Worksheets pipeline on your local machine.

## Prerequisites

- **Python 3.10+**
- **Ollama** installed and running locally (`http://localhost:11434` by default). It is required whatever LLM provider you choose, because embeddings for the Course Memory always run locally through Ollama (`EMBED_MODEL`). The LLM calls themselves can go to Ollama (the default), Anthropic, OpenAI or Gemini (`LLM_PROVIDER`).
- **Node.js** `^20.19` or `>=22.12` (only for the web app; required by Vite 8).
- A LaTeX distribution (e.g., MacTeX, TeX Live) or Overleaf if you want to compile the resulting `.tex` files into PDFs yourself. The app itself only writes `.tex`.

## 1. Setup the Python Environment

It is highly recommended to use a virtual environment to manage dependencies.

```bash
# Clone the repository and change into the repo root (the folder that contains main_cli.py)
cd ADHD-Worksheets

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

Run every command in this guide (CLI and `uvicorn`) from the repo root: the web Config page reads and writes `./.env`, and the pipeline cache is created in `./.pipeline_cache/`.

## 2. Configure Environment Variables

The pipeline uses environment variables to choose the LLM provider and the model for each LLM-backed step, so you can use heavy models for extraction and generation and a smaller model for knowledge-base tagging.

1. Copy the example configuration file:
   ```bash
   cp .env.example .env
   ```
   (If you skip this, the web app's Config page creates `.env` from `.env.example` the first time it is opened.)

2. Open `.env` and configure your provider and models. Settings are read when a process starts, so restart the backend after changing them.

   If you are using **Ollama** (default), ensure `OLLAMA_BASE` points to your active server (default: `http://localhost:11434`), and that you have pulled the required models (see step 3).

   If you are using **Anthropic**, **OpenAI** or **Gemini**, set `LLM_PROVIDER=anthropic|openai|gemini`, provide the matching API key, and set **all** of `MODEL_EXTRACTION`, `MODEL_PEDAGOGY`, `MODEL_WRITER`, `MODEL_QUESTIONS`, `TAG_MODEL` and `PAGEINDEX_MODEL` to model names that provider accepts. Every one of them is sent to the selected provider; the Ollama-style defaults will be rejected. `EMBED_MODEL` stays an Ollama model.

**Example `.env` configuration** (these are the defaults in `shared/config.py`):
```env
# General
LLM_PROVIDER=ollama
OLLAMA_BASE=http://localhost:11434
# ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# GEMINI_API_KEY=your_key_here

# --- Extraction pipeline ---
MODEL_EXTRACTION=gpt-oss:120b-cloud
MODEL_PEDAGOGY=gpt-oss:120b-cloud

# --- Generation pipeline (two calls per section) ---
MODEL_WRITER=gpt-oss:120b-cloud
MODEL_QUESTIONS=gpt-oss:120b-cloud

# --- Memory module (cmkb) ---
EMBED_MODEL=nomic-embed-text
TAG_MODEL=gemma3n:e4b
PAGEINDEX_MODEL=gemma3n:e4b
```

### All environment variables

| Variable | Default in code | Used for |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `anthropic`, `openai` or `gemini`. Used for every LLM call: extraction, generation, KB question tagging and alias generation, and PageIndex retrieval. PageIndex tree building at ingest (`--mode page_index`) only supports `ollama` and `openai`; any other value falls back to Ollama. |
| `OLLAMA_BASE` | `http://localhost:11434` | Ollama server. Always used for embeddings; also used for LLM calls when `LLM_PROVIDER=ollama`. |
| `OLLAMA_API_URL` | `$OLLAMA_BASE/api/generate` | Optional override of the generate endpoint used by the shared Ollama client. Rarely needed. |
| `ANTHROPIC_API_KEY` | (none) | Required when `LLM_PROVIDER=anthropic`. |
| `OPENAI_API_KEY` | (none) | Required when `LLM_PROVIDER=openai`. |
| `GEMINI_API_KEY` | (none) | Required when `LLM_PROVIDER=gemini`. |
| `ANTHROPIC_MAX_TOKENS` | `16384` | Output-token limit for Anthropic calls that do not set their own limit (KB tagging, alias generation, PageIndex retrieval). Extraction and generation calls use fixed per-stage limits (see [pipeline.md](pipeline.md)). |
| `MODEL_EXTRACTION` | `gpt-oss:120b-cloud` | Extraction Stage 1 (deck to section map). |
| `MODEL_PEDAGOGY` | `gpt-oss:120b-cloud` | Extraction Stage 2 (per-section annotation). |
| `MODEL_WRITER` | `gpt-oss:120b-cloud` | Generation Call A (Section Writer). |
| `MODEL_QUESTIONS` | `gpt-oss:120b-cloud` | Generation Call B (Question Set Builder). |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model (always local). A KB records its embedding model when created and refuses to work with a different one. |
| `TAG_MODEL` | `gemma3n:e4b` | Tagging questions at `memory ingest questions` and generating topic aliases at `memory cluster`. |
| `PAGEINDEX_MODEL` | `gemma3n:e4b` | PageIndex mode: tree building at ingest and tree traversal at query time. |
| `CHATGPT_API_KEY` | (none) | OpenAI key read by the vendored PageIndex code for tree building when `LLM_PROVIDER=openai` (it does not read `OPENAI_API_KEY`). `Ollama_API_KEY` is accepted as a legacy alias. |
| `OLLAMA_MODEL` | (none; falls back to `mistral24b-16k`) | PageIndex tree building with `LLM_PROVIDER=ollama` only: replaces `PAGEINDEX_MODEL` when that name contains `gpt-` or starts with `text-` (so `gpt-oss:*` names are swapped out). |
| `VITE_API_URL` | `http://localhost:8000/api` | Web app only. Set it in `web/.env.local`. It must include the `/api` suffix. |

The web app's Config page saves `LLM_PROVIDER`, `OLLAMA_BASE`, the three API keys, the four `MODEL_*` variables, `EMBED_MODEL`, `TAG_MODEL` and `PAGEINDEX_MODEL` to `.env` (empty fields are skipped). It also shows `ANTHROPIC_MAX_TOKENS` but does not save it; edit that and the other variables in `.env` directly.

## 3. Pull the Ollama Models

With the default `.env`:

```bash
ollama pull nomic-embed-text      # EMBED_MODEL: needed for any knowledge-base use
ollama pull gemma3n:e4b           # TAG_MODEL and PAGEINDEX_MODEL
ollama signin                     # gpt-oss:120b-cloud is an Ollama *cloud* model
ollama pull gpt-oss:120b-cloud    # MODEL_EXTRACTION / MODEL_PEDAGOGY / MODEL_WRITER / MODEL_QUESTIONS
```

Models ending in `-cloud` are served by Ollama's cloud (ollama.com) through your local Ollama, and need an ollama.com account. For fully local inference, set the four `MODEL_*` variables to a local model you have pulled instead.

If you use `--embed-model` or change `EMBED_MODEL`, pull that model too, and create the KB with the same name (`memory create ... --embed-model <name>`). `memory create` records `nomic-embed-text` unless you pass `--embed-model`.

## 4. Verify Installation

You can verify that the CLI is working correctly by checking the help menu:

```bash
python main_cli.py -h          # extract | generate | run
python main_cli.py memory -h   # knowledge-base commands (not listed by the first command)
```

## 5. Web App (optional)

```bash
cd web
npm install
npm run dev
```

See [web/README.md](../web/README.md) for details.

You are now ready to start using the pipeline. See [usage.md](usage.md) for instructions on running the tools.
