import json
import logging
from typing import List, Literal, Optional

from pydantic import BaseModel

from shared.config import MODEL_WRITER, MODEL_QUESTIONS
from shared.llm import generate_json
from generation.prompts import SYSTEM_PROMPT_SECTION_WRITER, SYSTEM_PROMPT_QUESTION_BUILDER

log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------

class NotationItem(BaseModel):
    symbol: str
    meaning: str


class WriterOutput(BaseModel):
    """Call A result: theory LaTeX, the symbols actually used, and a section
    summary (reused as the rolling-context entry and the memory-commit summary)."""
    theory: str
    notation: List[NotationItem] = []
    summary: str


class PracticeQuestion(BaseModel):
    level: Literal["recall", "understand", "apply", "analyse", "evaluate"]
    text: str
    answer: str = ""
    options: Optional[List[str]] = None


class PyqQuestion(BaseModel):
    id: Optional[str] = None  # echoes the candidate id, mapping back to the KB question
    text: str
    source: str = ""
    adapted: bool = False
    answer: str = ""
    options: Optional[List[str]] = None


class DeferredQuestion(BaseModel):
    id: Optional[str] = None
    text: str
    source: str = ""
    answer: str = ""
    reason: str = ""


class QuestionSet(BaseModel):
    """Call B result: the practice ladder, curated PYQs, and carry-forward items."""
    practice: List[PracticeQuestion] = []
    pyq: List[PyqQuestion] = []
    deferred: List[DeferredQuestion] = []


# ---------------------------------------------------------------------------
# Call A — Section Writer
# ---------------------------------------------------------------------------

def write_section(
    section_content: str,
    book_context: list,
    student_profile: str,
    prep_questions: list,
    learning_objectives: list,
    key_misconceptions: list,
) -> WriterOutput:
    log.info("  Writing section theory...")
    prompt = f"SOURCE CONTENT:\n{section_content}\n\n"

    if book_context:
        prompt += f"BOOK CONTEXT:\n{json.dumps(book_context, indent=2)}\n\n"

    prompt += f"STUDENT PROFILE:\n{student_profile}\n\n"

    if prep_questions:
        prompt += f"QUESTIONS TO PREPARE FOR:\n{json.dumps(prep_questions, indent=2)}\n\n"
    else:
        prompt += "QUESTIONS TO PREPARE FOR:\n(none matched for this section)\n\n"

    metadata = {
        "learning_objectives": learning_objectives,
        "key_misconceptions": key_misconceptions,
    }
    prompt += f"OBJECTIVES & MISCONCEPTIONS:\n{json.dumps(metadata, indent=2)}"

    return generate_json(
        prompt=prompt,
        model_name=MODEL_WRITER,
        system=SYSTEM_PROMPT_SECTION_WRITER,
        response_model=WriterOutput,
        max_tokens=16384,
    )


# ---------------------------------------------------------------------------
# Call B — Question Set Builder
# ---------------------------------------------------------------------------

def build_question_set(
    section_theory: str,
    candidates: list,
    student_profile: str,
    is_objective: bool,
) -> QuestionSet:
    log.info("  Building question set...")
    prompt = (
        f"SECTION THEORY:\n{section_theory}\n\n"
        f"CANDIDATES:\n{json.dumps(candidates, indent=2)}\n\n"
        f"STUDENT PROFILE:\n{student_profile}\n\n"
        f"OBJECTIVE MODE: {is_objective}"
    )

    return generate_json(
        prompt=prompt,
        model_name=MODEL_QUESTIONS,
        system=SYSTEM_PROMPT_QUESTION_BUILDER,
        response_model=QuestionSet,
        max_tokens=16384,
    )
