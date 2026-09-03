# cmkb configuration lives in shared.config — one source of truth for the
# whole repo (provider, models, embeddings, taxonomy tuning).
from shared.config import (  # noqa: F401
    OLLAMA_BASE,
    EMBED_MODEL,
    TAG_MODEL,
    PAGEINDEX_MODEL,
    CLUSTER_DISTANCE_THRESHOLD,
    TOPIC_MATCH_THRESHOLD,
)
