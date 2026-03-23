"""
Stage 1.5a — PYQ Extraction & Section Mapping
Stage 1.5b — Pedagogical Structuring

These two stages enrich the raw section map with PYQ mappings and
teaching metadata before per-section content generation begins.
"""

import json
from pathlib import Path

from src.llm import MODELS, call_ollama
from src.prompts import SYSTEM_PROMPT_PYQ_EXTRACTION, SYSTEM_PROMPT_PEDAGOGICAL
from src.stages.extraction import read_file_content


def run_pyq_extraction(
    extraction_data: dict,
    support_dir: str | None,
    cache,
) -> dict:
    """
    Stage 1.5a: Extract questions from support documents and map them to
    sections.

    Returns:
        dict with key "extracted_pyqs" containing the mapped questions list.
    """
    mapped_pyqs = cache.get_pyq_extraction()

    if mapped_pyqs:
        print("Stage 1.5a: Using cached PYQ extraction ✓")
        return mapped_pyqs

    section_map = extraction_data.get("section_map", [])

    # Determine support directory
    if support_dir:
        support_folder = Path(support_dir)
    else:
        support_folder = Path("src") / "supporting"

    if support_folder.exists():
        support_docs = list(support_folder.rglob("*.*"))
    else:
        support_docs = []
        print(
            f"  Warning: Support directory '{support_folder}' not found. "
            f"Stage 1.5a will have no input documents."
        )

    if support_docs:
        print("Stage 1.5a: Extracting and mapping PYQs from support documents...")

        section_titles_for_mapping = [
            {
                "section_title": s.get("section_title", ""),
                "topics": s.get("topics", []),
            }
            for s in section_map
        ]

        prompt_parts = ["--- SUPPORT DOCUMENTS ---"]
        for doc_path in support_docs:
            prompt_parts.append(f"\n=== {doc_path.name} ===")
            prompt_parts.append(read_file_content(doc_path))

        prompt_parts.append("\n--- SECTION MAP ---")
        prompt_parts.append(json.dumps(section_titles_for_mapping, indent=2))

        pyq_prompt = "\n".join(prompt_parts)

        pyq_response = call_ollama(
            model=MODELS["flash"],
            prompt=pyq_prompt,
            system=SYSTEM_PROMPT_PYQ_EXTRACTION,
            as_json=True,
        )

        try:
            mapped_pyqs = json.loads(pyq_response)
        except json.JSONDecodeError:
            print("  Warning: Failed to parse PYQ extraction JSON. Using empty list.")
            mapped_pyqs = {"extracted_pyqs": []}
    else:
        print("Stage 1.5a: No support documents found. Skipping PYQ extraction.")
        mapped_pyqs = {"extracted_pyqs": []}

    cache.set_pyq_extraction(mapped_pyqs)
    return mapped_pyqs


def run_pedagogical_structuring(
    extraction_data: dict,
    extracted_pyqs: list,
    section_map: list,
    cache,
) -> list:
    """
    Stage 1.5b: Annotate each section with pedagogical metadata.

    Returns:
        The enriched section map (list of section dicts with metadata).
    """
    enriched_section_map = cache.get_pedagogical()

    if enriched_section_map:
        print("Stage 1.5b: Using cached pedagogical metadata ✓")
    else:
        print("Stage 1.5b: Generating pedagogical structure...")

        ped_prompt_parts = [
            "--- STAGE 1 EXTRACTION JSON ---",
            json.dumps(extraction_data, indent=2),
            "\n--- MAPPED PYQS FROM STAGE 1.5a ---",
            json.dumps(extracted_pyqs, indent=2),
        ]

        ped_prompt = "\n".join(ped_prompt_parts)

        ped_response = call_ollama(
            model=MODELS["pro"],
            prompt=ped_prompt,
            system=SYSTEM_PROMPT_PEDAGOGICAL,
            as_json=True,
        )

        try:
            enriched_section_map = json.loads(ped_response)
            if (
                isinstance(enriched_section_map, dict)
                and "section_map" in enriched_section_map
            ):
                enriched_section_map = enriched_section_map["section_map"]
            elif isinstance(enriched_section_map, dict):
                enriched_section_map = enriched_section_map.get(
                    "section_map",
                    list(enriched_section_map.values())[0]
                    if enriched_section_map
                    else [],
                )
        except json.JSONDecodeError:
            print(
                "  Warning: Failed to parse pedagogical JSON. "
                "Falling back to raw section map."
            )
            enriched_section_map = section_map

        cache.set_pedagogical(enriched_section_map)

    if not isinstance(enriched_section_map, list):
        print("  Warning: enriched_section_map is not a list. Falling back.")
        enriched_section_map = section_map

    print(f"  Enriched sections: {len(enriched_section_map)}")
    return enriched_section_map
