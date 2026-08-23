import json
from pathlib import Path

from shared.cache import PipelineCache
from extraction.stages import (
    run_extraction,
    run_question_extraction,
    run_pedagogical_structuring,
)


def run_extraction_pipeline(pdf_path: Path, output_json_path: Path):
    """
    Runs the complete extraction pipeline:
    1. Parse PDF and extract content (Stage 1)
    2. Extract internal lecture questions (Stage 1.5a)
    3. Generate pedagogical structure (Stage 1.5b)
    """
    print(f"Starting extraction pipeline for {pdf_path.name}...")
    
    cache = PipelineCache(pdf_path)

    # Stage 1: Extraction
    extraction_data = run_extraction(pdf_path, cache=cache)

    # Stage 1.5a: Question Extraction
    questions_data = run_question_extraction(extraction_data, cache=cache)
    extracted_questions = questions_data.get("extracted_questions", [])

    # Stage 1.5b: Pedagogical Structuring
    pedagogical_json = run_pedagogical_structuring(
        extraction_data, extracted_questions, cache=cache
    )

    # Save final JSON
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(pedagogical_json, f, indent=2)

    print(f"\nExtraction complete! Pedagogical JSON saved to: {output_json_path}")
    return pedagogical_json
