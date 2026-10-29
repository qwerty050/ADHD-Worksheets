import json
import logging
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

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


# Structural formatting belongs to the renderer, not to the content. Text
# fields are Markdown with TeX math; document-level LaTeX structure and
# unescaped backslashes are rejected so the model is asked to repair them
# (generate_json repair retries).
_STRUCTURAL_LATEX_RE = re.compile(
    r"\\(?:(?:sub)*section|chapter|part|documentclass)\b\*?|\\begin\{document\}"
)


def _check_markup(value: str) -> str:
    # "\frac" or "\beta" with a single backslash in JSON decodes to a
    # form-feed / backspace character: the LaTeX is silently corrupted.
    if "\f" in (value or "") or "\b" in (value or ""):
        raise ValueError(
            "contains a form-feed/backspace character: a backslash was not escaped "
            "(write \\\\frac, not \\frac, inside JSON strings)"
        )
    m = _STRUCTURAL_LATEX_RE.search(value or "")
    if m:
        raise ValueError(
            f"contains the LaTeX structure command '{m.group(0)}'; write Markdown "
            f"with TeX math only (headings come from the JSON fields)"
        )
    return value


class WorkedExample(BaseModel):
    problem: str = Field(min_length=1)
    steps: List[str] = Field(min_length=1)
    answer: str = Field(min_length=1)
    insight: str = Field(min_length=1)  # one sentence: what the example demonstrates

    @field_validator("problem", "answer", "insight")
    @classmethod
    def _check_text(cls, v: str) -> str:
        return _check_markup(v)

    @field_validator("steps")
    @classmethod
    def _check_steps(cls, v: List[str]) -> List[str]:
        return [_check_markup(s) for s in v]


class Theory(BaseModel):
    """The five theory parts, in reading order. Markdown with TeX math."""
    motivation: str = Field(min_length=1)
    intuition: str = Field(min_length=1)
    formal_content: str = Field(min_length=1)
    worked_example: Optional[WorkedExample] = None  # only for numeric/procedural content
    key_takeaway: str = Field(min_length=1)

    @field_validator("motivation", "intuition", "formal_content", "key_takeaway")
    @classmethod
    def _check_text(cls, v: str) -> str:
        return _check_markup(v)


class WriterOutput(BaseModel):
    """Call A result: structured theory, the symbols actually used, and a section
    summary (reused as the rolling-context entry and the memory-commit summary)."""
    theory: Theory
    notation: List[NotationItem] = []
    summary: str = Field(min_length=1)


def theory_as_text(theory: Theory) -> str:
    """Plain reading-order text of the theory, used as Call B's ground truth."""
    parts = [
        f"## Motivation\n{theory.motivation}",
        f"## Intuition\n{theory.intuition}",
        f"## Formal Content\n{theory.formal_content}",
    ]
    we = theory.worked_example
    if we:
        steps = "\n".join(f"{n}. {step}" for n, step in enumerate(we.steps, 1))
        parts.append(
            f"## Worked Example\nProblem: {we.problem}\n{steps}\n"
            f"Answer: {we.answer}\n{we.insight}"
        )
    parts.append(f"## Key Takeaway\n{theory.key_takeaway}")
    return "\n\n".join(parts)


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
