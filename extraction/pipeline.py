import json
import logging
from pathlib import Path

from shared.cache import PipelineCache
from extraction.stages import extract_section_map, annotate_section

log = logging.getLogger("pipeline")


def run_extraction_pipeline(pdf_path: Path, output_json_path: Path, cache: PipelineCache = None) -> list:
    """
    Extract a pedagogical JSON from a lecture PDF:
    1. Stage 1: whole-deck section map (chunked if over budget)
    2. Stage 2: one small annotation call per section (objectives, misconceptions,
       worked-example spec, embedded questions)
    3. Deterministic merge into the final section list.

    Failures raise; only validated output is cached.
    """
    log.info("Starting extraction pipeline for %s...", pdf_path.name)

    if cache is None:
        cache = PipelineCache(pdf_path)

    sections = extract_section_map(pdf_path, cache=cache)

    pedagogical_json = []
    for i, section in enumerate(sections):
        annotation = annotate_section(section, cache=cache, section_idx=i)
        pedagogical_json.append({
            **section.model_dump(),
            **annotation.model_dump(),
        })

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(pedagogical_json, f, indent=2)

    log.info("Extraction complete! Pedagogical JSON saved to: %s", output_json_path)
    return pedagogical_json
