import json
import requests
import numpy as np
from .config import OLLAMA_BASE, EMBED_MODEL, TAG_MODEL

def _embed_payload(texts: list[str], task: str) -> dict:
    prefix = "search_query: " if task == "query" else "search_document: "
    return {"model": EMBED_MODEL, "input": [prefix + t for t in texts]}

def ollama_embed_batch(texts: list[str], task: str = "document") -> list[np.ndarray]:
    """Batch embedding via Ollama's /api/embed endpoint. task must be 'query'
    or 'document'; nomic-embed-text was trained with these prefixes and gives
    noticeably worse/unstable similarity without them."""
    if not texts:
        return []
    resp = requests.post(
        f"{OLLAMA_BASE}/api/embed",
        json=_embed_payload(texts, task),
        timeout=120,
    )
    resp.raise_for_status()
    embeddings = resp.json().get("embeddings", [])
    if len(embeddings) != len(texts):
        raise ValueError(f"Ollama embed returned {len(embeddings)} vectors for {len(texts)} inputs")
    return [np.array(e, dtype="float32") for e in embeddings]

def ollama_embed(text: str, task: str = "document") -> np.ndarray:
    return ollama_embed_batch([text], task)[0]

def ollama_generate_json(system_prompt: str, user_prompt: str, schema: dict = None) -> list:
    """JSON generation for KB tagging/aliasing via the shared LLM client
    (works on any provider; schema is kept for Ollama call-site compatibility
    but enforcement relies on the prompt). Raises on unparseable output."""
    from shared.llm import get_llm_client
    client = get_llm_client()
    raw = client.generate(
        prompt=user_prompt,
        model_name=TAG_MODEL,
        system=system_prompt,
        as_json=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse response as JSON: {raw[:500]}")

def traverse_page_index(query: str, node: dict, breadcrumb: str = "") -> list:
    """
    Recursively traverses the PageIndex tree using an LLM to select relevant branches.
    Returns a list of dicts: [{"text": full_text, "heading_path": breadcrumb, "page_range": [start, end]}]
    """
    from .config import PAGEINDEX_MODEL
    
    current_title = node.get("title", "")
    current_breadcrumb = f"{breadcrumb} > {current_title}" if breadcrumb else current_title
    
    children = node.get("children", [])
    if not children:
        # Leaf node
        return [{
            "text": node.get("text", ""),
            "heading_path": current_breadcrumb,
            "page_range": [node.get("physical_index", 0), node.get("physical_index", 0)]
        }]
    
    # Not a leaf node, we need to ask the LLM which children to explore
    child_summaries = []
    for i, child in enumerate(children):
        title = child.get("title", "Untitled")
        summary = child.get("summary", "No summary available.")
        child_summaries.append(f"[{i}] {title}: {summary}")

    system_prompt = (
        "You are an intelligent retrieval agent. You are given a user query and a list of "
        "document sections with their summaries. Your task is to select which sections might "
        "contain the answer to the query.\n"
        "Return a JSON array of the integer indices of the sections to explore.\n"
        "Output ONLY the JSON array, e.g., [0, 2]"
    )

    user_prompt = f"Query: {query}\n\nSections:\n" + "\n".join(child_summaries)

    from shared.llm import get_llm_client

    try:
        raw = get_llm_client().generate(
            prompt=user_prompt,
            model_name=PAGEINDEX_MODEL,
            system=system_prompt,
            as_json=True,
        )
        selected_indices = json.loads(raw)
    except Exception as e:
        print(f"Error traversing tree for query '{query}': {e}")
        selected_indices = []  # Default to empty if LLM fails
        
    results = []
    for idx in selected_indices:
        if 0 <= idx < len(children):
            results.extend(traverse_page_index(query, children[idx], current_breadcrumb))
            
    return results
