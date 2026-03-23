"""
Stage 1 — Parsing / Extraction.

Reads a PDF slide + support documents + context files, calls the LLM
extraction prompt, and returns structured JSON with a section map.
"""

import json
from pathlib import Path

from src.llm import MODELS, call_ollama
from src.prompts import SYSTEM_PROMPT_GLOBAL_EXTRACTION


def read_file_content(path: Path) -> str:
    """Read text content from a file, handling PDFs and binary gracefully."""
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            return text
        except ImportError:
            return (
                f"[Missing PyMuPDF (fitz) library to read {path.name}. "
                f"Run `pip install PyMuPDF`]"
            )
        except Exception as e:
            return f"[Failed to read PDF {path.name}: {e}]"

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return f"[Cannot decode {path.name} as text.]"


def run_extraction(
    source_folder: str,
    target_slide_name: str,
    cache=None,
) -> dict:
    """
    Stage 1: Extract content from a PDF slide into a structured JSON
    section map.

    Args:
        source_folder:     Path to the folder containing the target slide.
        target_slide_name: Filename of the target slide (e.g. "W5M1.pdf").
        cache:             Optional PipelineCache instance.

    Returns:
        dict with keys: cleaned_content, prerequisite_gaps, section_map,
        extracted_pyqs.
    """
    source = Path(source_folder)
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source}")

    target_slide = source / target_slide_name
    if not target_slide.exists():
        raise FileNotFoundError(f"Target slide not found: {target_slide}")

    # Check cache
    if cache:
        cached = cache.get_extraction()
        if cached:
            print("Stage 1: Using cached extraction ✓")
            return cached

    print("Stage 1: Reading files and extracting content...")

    # Gather supporting docs and context files
    supporting_folder = source / "supporting"
    context_folder = source / "context"

    supporting_docs = (
        list(supporting_folder.rglob("*.*"))
        if supporting_folder.exists()
        else list(source.glob("support*.*"))
    )
    context_files = (
        list(context_folder.rglob("*.*"))
        if context_folder.exists()
        else list(source.glob("context*.*"))
    )

    # Build prompt
    prompt_parts = [f"Target Slide Content:\n{read_file_content(target_slide)}\n"]

    if context_files:
        prompt_parts.append("--- PREVIOUS CONTEXT ---")
        for f in context_files:
            prompt_parts.append(read_file_content(f))

    if supporting_docs:
        prompt_parts.append("--- SUPPORTING DOCS ---")
        for f in supporting_docs:
            prompt_parts.append(read_file_content(f))

    combined_prompt = "\n".join(prompt_parts)

    response_text = call_ollama(
        model=MODELS["pro"],
        prompt=combined_prompt,
        system=SYSTEM_PROMPT_GLOBAL_EXTRACTION,
        as_json=True,
    )

    try:
        extraction_data = json.loads(response_text)
    except json.JSONDecodeError:
        print("  Warning: Failed to parse extraction JSON. Using empty map.")
        extraction_data = {"section_map": [], "extracted_pyqs": []}

    if cache:
        cache.set_extraction(extraction_data)

    return extraction_data
