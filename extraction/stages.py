import json
from pathlib import Path
import pymupdf  # PyMuPDF

from shared.llm import get_llm_client
from shared.config import MODEL_EXTRACTION, MODEL_QUESTION_EXTRACT, MODEL_PEDAGOGY
from extraction.prompts import (
    SYSTEM_PROMPT_GLOBAL_EXTRACTION,
    SYSTEM_PROMPT_QUESTION_EXTRACTION,
    SYSTEM_PROMPT_PEDAGOGICAL,
)


def read_file_content(path: Path) -> str:
    """Read text content from a file, handling PDFs gracefully."""
    if path.suffix.lower() == ".pdf":
        try:
            doc = pymupdf.open(path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            return text
        except Exception as e:
            return f"[Failed to read PDF {path.name}: {e}]"

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return f"[Cannot decode {path.name} as text.]"


def run_extraction(
    target_slide_path: Path,
    cache=None,
) -> dict:
    """
    Stage 1: Extract content from a PDF slide into a structured JSON section map.
    """
    if not target_slide_path.exists():
        raise FileNotFoundError(f"Target slide not found: {target_slide_path}")

    # Check cache
    if cache:
        cached = cache.get_extraction()
        if cached:
            print("Stage 1: Using cached extraction ✓")
            return cached

    print("Stage 1: Reading PDF and extracting content...")

    prompt = f"Target Slide Content:\n{read_file_content(target_slide_path)}\n"

    response_text = get_llm_client().generate(
        prompt=prompt,
        model_name=MODEL_EXTRACTION,
        system=SYSTEM_PROMPT_GLOBAL_EXTRACTION,
        as_json=True,
    )

    try:
        extraction_data = json.loads(response_text)
    except json.JSONDecodeError:
        print("  Warning: Failed to parse extraction JSON. Using empty map.")
        extraction_data = {"section_map": [], "extracted_questions": []}

    if cache:
        cache.set_extraction(extraction_data)

    return extraction_data


def run_question_extraction(
    extraction_data: dict,
    cache=None,
) -> dict:
    """
    Stage 1.5a: Extract questions embedded in the lecture PDF itself.
    Uses the cleaned_content from Stage 1 as the source.
    """
    if cache:
        mapped_questions = cache.get_question_extraction()
        if mapped_questions:
            print("Stage 1.5a: Using cached question extraction ✓")
            return mapped_questions

    print("Stage 1.5a: Extracting lecture-internal questions...")

    section_map = extraction_data.get("section_map", [])
    section_titles_for_mapping = [
        {
            "section_title": s.get("section_title", ""),
            "topics": s.get("topics", []),
        }
        for s in section_map
    ]

    cleaned_content = extraction_data.get("cleaned_content", "")
    
    prompt_parts = [
        "--- LECTURE SLIDE CONTENT ---",
        cleaned_content,
        "\n--- SECTION MAP ---",
        json.dumps(section_titles_for_mapping, indent=2)
    ]

    question_prompt = "\n".join(prompt_parts)

    question_response = get_llm_client().generate(
        prompt=question_prompt,
        model_name=MODEL_QUESTION_EXTRACT,
        system=SYSTEM_PROMPT_QUESTION_EXTRACTION,
        as_json=True,
    )

    try:
        mapped_questions = json.loads(question_response)
    except json.JSONDecodeError:
        print("  Warning: Failed to parse question extraction JSON. Using empty list.")
        mapped_questions = {"extracted_questions": []}

    if cache:
        cache.set_question_extraction(mapped_questions)
    return mapped_questions


def run_pedagogical_structuring(
    extraction_data: dict,
    extracted_questions: list,
    cache=None,
) -> list:
    """
    Stage 1.5b: Annotate each section with pedagogical metadata.
    """
    if cache:
        enriched_section_map = cache.get_pedagogical()
        if enriched_section_map:
            print("Stage 1.5b: Using cached pedagogical metadata ✓")
            return enriched_section_map

    print("Stage 1.5b: Generating pedagogical structure...")

    ped_prompt_parts = [
        "--- STAGE 1 EXTRACTION JSON ---",
        json.dumps(extraction_data, indent=2),
        "\n--- MAPPED LECTURE QUESTIONS FROM STAGE 1.5a ---",
        json.dumps(extracted_questions, indent=2),
    ]

    ped_prompt = "\n".join(ped_prompt_parts)

    ped_response = get_llm_client().generate(
        prompt=ped_prompt,
        model_name=MODEL_PEDAGOGY,
        system=SYSTEM_PROMPT_PEDAGOGICAL,
        as_json=True,
    )

    section_map = extraction_data.get("section_map", [])

    try:
        enriched_section_map = json.loads(ped_response)
        if isinstance(enriched_section_map, dict) and "section_map" in enriched_section_map:
            enriched_section_map = enriched_section_map["section_map"]
        elif isinstance(enriched_section_map, dict):
            enriched_section_map = enriched_section_map.get(
                "section_map",
                list(enriched_section_map.values())[0] if enriched_section_map else [],
            )
    except json.JSONDecodeError:
        print("  Warning: Failed to parse pedagogical JSON. Falling back to raw section map.")
        enriched_section_map = section_map

    if not isinstance(enriched_section_map, list):
        print("  Warning: enriched_section_map is not a list. Falling back.")
        enriched_section_map = section_map

    if cache:
        cache.set_pedagogical(enriched_section_map)

    print(f"  Enriched sections: {len(enriched_section_map)}")
    return enriched_section_map
