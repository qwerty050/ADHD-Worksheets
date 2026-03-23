#!/usr/bin/env python3
"""
AI Learning Module Generator — Unified Entry Point.

Usage:
    # From a PDF (runs full pipeline: extraction → pedagogy → sections)
    python main.py slides/W5M1.pdf --support-dir slides/supporting/

    # From a pre-extracted JSON (skips Stage 1)
    python main.py json/w5m1.json

    # With options
    python main.py json/w5m1.json --objective --review --no-newpage
"""

import argparse
import json
import sys
from pathlib import Path

from src.cache import PipelineCache
from src.stages.extraction import run_extraction
from src.stages.pedagogy import run_pyq_extraction, run_pedagogical_structuring
from src.stages.sections import process_all_sections


def run_pipeline(
    input_path: str,
    is_objective: bool = False,
    review: bool = False,
    newpage_per_question: bool = True,
    support_dir: str | None = None,
) -> dict:
    """
    Run the full learning module generation pipeline.

    Automatically detects whether the input is a PDF (runs Stage 1 first)
    or a JSON file (skips to Stage 1.5a).

    Returns:
        dict with keys "latex" and "context".
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    cache = PipelineCache(input_file)
    if cache.has_cached_progress():
        print("PipelineCache: Resuming from cached progress.")

    # -----------------------------------------------------------------
    # Determine input type and get extraction data
    # -----------------------------------------------------------------
    if input_file.suffix.lower() == ".pdf":
        print(f"Input is a PDF — running Stage 1 extraction first.")
        source_folder = str(input_file.parent)
        target_slide_name = input_file.name

        extraction_data = run_extraction(
            source_folder=source_folder,
            target_slide_name=target_slide_name,
            cache=cache,
        )

        # Save the extracted JSON for future re-runs
        json_output_dir = Path("json")
        json_output_dir.mkdir(exist_ok=True)
        json_out_path = json_output_dir / f"{input_file.stem}.json"
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(extraction_data, f, indent=2)
        print(f"  Extraction saved to {json_out_path}")

    elif input_file.suffix.lower() == ".json":
        print(f"Input is JSON — skipping Stage 1.")
        with open(input_file, "r", encoding="utf-8") as f:
            extraction_data = json.load(f)
    else:
        raise ValueError(
            f"Unsupported input format: {input_file.suffix}. "
            f"Use .pdf or .json"
        )

    section_map = extraction_data.get("section_map", [])
    if not section_map:
        raise Exception("Failed to load Section Map from input.")

    # -----------------------------------------------------------------
    # Stage 1.5a: PYQ Extraction & Section Mapping
    # -----------------------------------------------------------------
    if support_dir:
        mapped_pyqs = run_pyq_extraction(
            extraction_data=extraction_data,
            support_dir=support_dir,
            cache=cache,
        )
        extracted_pyqs = mapped_pyqs.get("extracted_pyqs", [])
        print(f"  PYQs extracted: {len(extracted_pyqs)}")
    else:
        print("Stage 1.5a: Skipped (no --support-dir provided).")
        extracted_pyqs = []

    # -----------------------------------------------------------------
    # Stage 1.5b: Pedagogical Structuring
    # -----------------------------------------------------------------
    enriched_section_map = run_pedagogical_structuring(
        extraction_data=extraction_data,
        extracted_pyqs=extracted_pyqs,
        section_map=section_map,
        cache=cache,
    )

    # -----------------------------------------------------------------
    # Stages 2 + 3: Per-section processing + Formatting
    # -----------------------------------------------------------------
    result = process_all_sections(
        enriched_section_map=enriched_section_map,
        extracted_pyqs=extracted_pyqs,
        cache=cache,
        target_json=input_file,
        is_objective=is_objective,
        review=review,
        newpage_per_question=newpage_per_question,
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="AI Learning Module Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python main.py slides/W5M1.pdf
  python main.py json/w5m1.json --objective --review
  python main.py json/w5m1.json --no-newpage --support-dir ./past_papers/
""",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to input file (.pdf for full pipeline, .json to skip extraction)",
    )
    parser.add_argument(
        "--objective",
        action="store_true",
        help="Enable objective mode (generate MCQs)",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        default=False,
        help="Enable review pass (default: off)",
    )
    parser.add_argument(
        "--no-newpage",
        dest="newpage",
        action="store_false",
        default=True,
        help="Disable \\newpage between questions",
    )
    parser.add_argument(
        "--support-dir",
        type=str,
        default=None,
        help="Path to support documents directory (default: src/supporting/)",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    print(f"Starting pipeline with input: {input_file}")
    print(f"  Objective mode:      {args.objective}")
    print(f"  Review pass:         {args.review}")
    print(f"  Newpage per question: {args.newpage}")
    if args.support_dir:
        print(f"  Support dir:         {args.support_dir}")

    try:
        result = run_pipeline(
            input_path=args.input,
            is_objective=args.objective,
            review=args.review,
            newpage_per_question=args.newpage,
            support_dir=args.support_dir,
        )
    except Exception as e:
        print(f"\nPipeline Error: {e}")
        print("PipelineCache: Progress saved. Retry to resume.")
        sys.exit(1)

    # Save outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    stem = input_file.stem

    tex_path = output_dir / f"{stem}_module.tex"
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(result["latex"])

    ctx_path = output_dir / f"{stem}_context.txt"
    with open(ctx_path, "w", encoding="utf-8") as f:
        f.write(result["context"])

    print(f"\nOutput saved to {tex_path}")


if __name__ == "__main__":
    main()
