import json
import logging
from pathlib import Path
from typing import List, Literal, Optional

import pymupdf  # PyMuPDF
from pydantic import BaseModel

from shared.config import MODEL_EXTRACTION, MODEL_PEDAGOGY
from shared.llm import generate_json
from extraction.prompts import (
    SYSTEM_PROMPT_SECTION_MAP,
    SYSTEM_PROMPT_SECTION_ANNOTATION,
)

log = logging.getLogger("pipeline")

# Characters per Stage-1 chunk (~75k tokens). Decks larger than this are split
# into page-range chunks and their section maps concatenated deterministically.
EXTRACT_BUDGET_CHARS = 300_000


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------

class ExtractedSection(BaseModel):
    section_title: str
    section_content: str
    topics: List[str] = []
    subtopics: List[str] = []
    dependency_order: int = 0


class SectionMapOutput(BaseModel):
    section_map: List[ExtractedSection]


class LectureQuestion(BaseModel):
    text: str
    type: Literal["numerical", "conceptual", "derivation", "design", "mcq"] = "conceptual"
    difficulty: Literal["recall", "understand", "apply", "analyse", "evaluate"] = "understand"
    assumed_knowledge: List[str] = []


class SectionAnnotation(BaseModel):
    learning_objectives: List[str] = []
    key_misconceptions: List[str] = []
    worked_example_spec: str = ""
    extracted_questions: List[LectureQuestion] = []


# ---------------------------------------------------------------------------
# PDF reading
# ---------------------------------------------------------------------------

def read_pdf_pages(path: Path) -> list[str]:
    """Per-page text with page markers. Raises on unreadable PDFs — a corrupt
    or scanned file must not silently become LLM prompt content."""
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages = []
    try:
        doc = pymupdf.open(path)
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            pages.append(f"--- Page {i + 1} ---\n{text}")
        doc.close()
    except Exception as e:
        raise RuntimeError(f"Could not read PDF {path.name}: {e}") from e

    if not any(p.split("\n", 1)[-1].strip() for p in pages):
        raise RuntimeError(
            f"PDF {path.name} contains no extractable text (scanned/image-only?). "
            "OCR is not supported."
        )
    return pages


# ---------------------------------------------------------------------------
# Stage 1 — Section Map
# ---------------------------------------------------------------------------

def _extract_chunk(pages_text: str, prior_titles: List[str]) -> SectionMapOutput:
    prompt = f"LECTURE DECK CONTENT:\n{pages_text}\n"
    if prior_titles:
        prompt += (
            f"\nSections already extracted from earlier pages (do not repeat them, "
            f"continue the numbering): {json.dumps(prior_titles)}"
        )
    return generate_json(
        prompt=prompt,
        model_name=MODEL_EXTRACTION,
        system=SYSTEM_PROMPT_SECTION_MAP,
        response_model=SectionMapOutput,
        max_tokens=16384,
    )


def extract_section_map(pdf_path: Path, cache=None) -> List[ExtractedSection]:
    if cache:
        cached = cache.get_extraction()
        if cached:
            log.info("Stage 1: Using cached section map")
            return [ExtractedSection.model_validate(s) for s in cached]

    log.info("Stage 1: Reading PDF and extracting section map...")
    pages = read_pdf_pages(pdf_path)

    full_text = "\n\n".join(pages)
    if len(full_text) <= EXTRACT_BUDGET_CHARS:
        sections = _extract_chunk(full_text, []).section_map
    else:
        log.warning(
            "Deck is %.0fk chars (> %dk budget) — splitting into page-range chunks.",
            len(full_text) / 1000, EXTRACT_BUDGET_CHARS / 1000,
        )
        sections = []
        chunk: list[str] = []
        chunk_chars = 0
        chunks: list[list[str]] = []
        for page in pages:
            if chunk and chunk_chars + len(page) > EXTRACT_BUDGET_CHARS:
                chunks.append(chunk)
                chunk, chunk_chars = [], 0
            chunk.append(page)
            chunk_chars += len(page)
        if chunk:
            chunks.append(chunk)

        for chunk_pages in chunks:
            chunk_map = _extract_chunk("\n\n".join(chunk_pages), [s.section_title for s in sections])
            sections.extend(chunk_map.section_map)

    # Deterministic renumbering after concatenation
    for i, s in enumerate(sections):
        s.dependency_order = i + 1

    if cache:
        cache.set_extraction([s.model_dump() for s in sections])
    log.info("Stage 1: %d sections", len(sections))
    return sections


# ---------------------------------------------------------------------------
# Stage 2 — Per-Section Annotation
# ---------------------------------------------------------------------------

def annotate_section(section: ExtractedSection, cache=None, section_idx: int = None) -> SectionAnnotation:
    if cache is not None and section_idx is not None:
        cached = cache.get_section_step(section_idx, "annotate")
        if cached:
            return SectionAnnotation.model_validate_json(cached)

    log.info("Stage 2: Annotating section %d: %s", section_idx + 1 if section_idx is not None else 0, section.section_title)
    prompt = (
        f"SECTION TITLE: {section.section_title}\n\n"
        f"SECTION TOPICS: {', '.join(section.topics + section.subtopics)}\n\n"
        f"SECTION CONTENT:\n{section.section_content}"
    )
    annotation = generate_json(
        prompt=prompt,
        model_name=MODEL_PEDAGOGY,
        system=SYSTEM_PROMPT_SECTION_ANNOTATION,
        response_model=SectionAnnotation,
        max_tokens=8192,
    )

    if cache is not None and section_idx is not None:
        cache.set_section_step(section_idx, "annotate", annotation.model_dump_json())
    return annotation
