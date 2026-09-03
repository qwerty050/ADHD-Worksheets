import os
from dotenv import load_dotenv

load_dotenv()

# General
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", f"{OLLAMA_BASE}/api/generate")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "16384"))

# Extraction
MODEL_EXTRACTION = os.getenv("MODEL_EXTRACTION", "gpt-oss:120b-cloud")  # Stage 1: deck -> section map
MODEL_PEDAGOGY = os.getenv("MODEL_PEDAGOGY", "gpt-oss:120b-cloud")      # Stage 2: per-section annotation

# Generation (two calls per section)
MODEL_WRITER = os.getenv("MODEL_WRITER", "gpt-oss:120b-cloud")          # Call A: section theory
MODEL_QUESTIONS = os.getenv("MODEL_QUESTIONS", "gpt-oss:120b-cloud")    # Call B: question set builder

# Memory
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
TAG_MODEL = os.getenv("TAG_MODEL", "gemma3n:e4b")
PAGEINDEX_MODEL = os.getenv("PAGEINDEX_MODEL", "gemma3n:e4b")

# Topic taxonomy tuning
CLUSTER_DISTANCE_THRESHOLD = 0.22
TOPIC_MATCH_THRESHOLD = 0.35
