import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
TAG_MODEL = os.getenv("TAG_MODEL", "gemma3n:e4b")
PAGEINDEX_MODEL = os.getenv("PAGEINDEX_MODEL", "gemma4:e4b")

CLUSTER_DISTANCE_THRESHOLD = 0.22
TOPIC_MATCH_THRESHOLD = 0.35
