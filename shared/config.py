import os
from dotenv import load_dotenv

load_dotenv()

# General
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", f"{OLLAMA_BASE}/api/generate")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Extraction
MODEL_EXTRACTION = os.getenv("MODEL_EXTRACTION", "gpt-oss:120b-cloud")
MODEL_QUESTION_EXTRACT = os.getenv("MODEL_QUESTION_EXTRACT", "gpt-oss:20b-cloud")
MODEL_PEDAGOGY = os.getenv("MODEL_PEDAGOGY", "gpt-oss:120b-cloud")

# Generation
MODEL_THEORY = os.getenv("MODEL_THEORY", "gpt-oss:120b-cloud")
MODEL_QUESTIONS = os.getenv("MODEL_QUESTIONS", "gpt-oss:120b-cloud")
MODEL_QUESTION_FILTER = os.getenv("MODEL_QUESTION_FILTER", "gpt-oss:20b-cloud")
MODEL_REVIEW = os.getenv("MODEL_REVIEW", "gpt-oss:20b-cloud")
MODEL_CONTEXT_SUMMARY = os.getenv("MODEL_CONTEXT_SUMMARY", "gpt-oss:20b-cloud")

# Memory
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
TAG_MODEL = os.getenv("TAG_MODEL", "gemma3n:e4b")
PAGEINDEX_MODEL = os.getenv("PAGEINDEX_MODEL", "gemma3n:e4b")
