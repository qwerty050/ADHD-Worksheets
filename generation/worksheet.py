"""
Worksheet JSON: the generation pipeline's output contract (schema v1).

Content only, no formatting. Text fields are Markdown with TeX math
($...$ inline, $$...$$ display); a separate formatter turns this into LaTeX
or any other target. Assembly is deterministic: no LLM calls here.
See docs/WORKSHEET_JSON_SCHEMA.md.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel

from generation.stages import NotationItem, QuestionSet, Theory, WriterOutput

WORKSHEET_SCHEMA = "adhd-worksheet"
WORKSHEET_SCHEMA_VERSION = 1
CONTENT_FORMAT = "markdown+tex"


class PracticeItem(BaseModel):
    number: int  # 1-based, sequential per section across practice then past-year questions
    level: Literal["recall", "understand", "apply", "analyse", "evaluate"]
    text: str
    options: Optional[List[str]] = None  # objective mode: option texts, answer is a letter A-D
    answer: str = ""


class PastYearItem(BaseModel):
    number: int
    text: str
    source: str = ""
    adapted: bool = False
    candidate_id: Optional[str] = None  # "kb:<pk>", "lec:<s>:<j>" or a carried deferred id
    options: Optional[List[str]] = None
    answer: str = ""


class WorksheetSection(BaseModel):
    index: int  # 1-based position in the worksheet
    title: str
    topics: List[str] = []
    learning_objectives: List[str] = []
    notation: List[NotationItem] = []  # symbol is TeX math without $ delimiters
    theory: Theory
    practice_questions: List[PracticeItem] = []
    past_year_questions: List[PastYearItem] = []
    summary: str


class UnplacedQuestion(BaseModel):
    """A candidate that every section deferred (stays unused in memory)."""
    text: str
    source: str = ""
    reason: str = ""


class RenderHints(BaseModel):
    """Presentation preferences for the formatter. Not content."""
    newpage_per_question: bool = True


class Worksheet(BaseModel):
    schema_name: Literal["adhd-worksheet"] = WORKSHEET_SCHEMA
    schema_version: Literal[1] = WORKSHEET_SCHEMA_VERSION
    content_format: Literal["markdown+tex"] = CONTENT_FORMAT
    title: str
    lecture_id: Optional[str] = None
    generated_at: str  # UTC, ISO 8601
    objective_mode: bool = False
    render_hints: RenderHints = RenderHints()
    sections: List[WorksheetSection] = []
    unplaced_questions: List[UnplacedQuestion] = []


def _clean_symbol(symbol: str) -> str:
    return (symbol or "").strip().strip("$").strip()


def build_section(
    index: int,
    section: dict,
    writer_output: WriterOutput,
    question_set: QuestionSet,
) -> WorksheetSection:
    """Combine the pedagogical section and both LLM results into one section record."""
    number = 0
    practice = []
    for q in question_set.practice:
        number += 1
        practice.append(PracticeItem(
            number=number, level=q.level, text=q.text, options=q.options, answer=q.answer,
        ))
    past_year = []
    for q in question_set.pyq:
        number += 1
        past_year.append(PastYearItem(
            number=number, text=q.text, source=q.source or "past exam", adapted=q.adapted,
            candidate_id=q.id, options=q.options, answer=q.answer,
        ))

    return WorksheetSection(
        index=index,
        title=section.get("section_title") or f"Section {index}",
        topics=list(section.get("topics", []) or []) + list(section.get("subtopics", []) or []),
        learning_objectives=list(section.get("learning_objectives", []) or []),
        notation=[
            NotationItem(symbol=_clean_symbol(n.symbol), meaning=n.meaning)
            for n in writer_output.notation
        ],
        theory=writer_output.theory,
        practice_questions=practice,
        past_year_questions=past_year,
        summary=writer_output.summary,
    )


def build_worksheet(
    title: str,
    lecture_id: Optional[str],
    sections: List[WorksheetSection],
    unplaced: List[dict],
    is_objective: bool,
    newpage_per_question: bool,
) -> Worksheet:
    return Worksheet(
        title=title,
        lecture_id=lecture_id,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        objective_mode=is_objective,
        render_hints=RenderHints(newpage_per_question=newpage_per_question),
        sections=sections,
        unplaced_questions=[
            UnplacedQuestion(text=d.get("text", ""), source=d.get("source", ""), reason=d.get("reason", ""))
            for d in unplaced
        ],
    )
