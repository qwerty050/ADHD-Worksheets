import json
import logging
from pathlib import Path

from shared.cache import PipelineCache
from generation.stages import (
    write_section,
    build_question_set,
    theory_as_text,
    WriterOutput,
    QuestionSet,
)
from generation.worksheet import build_section, build_worksheet

log = logging.getLogger("pipeline")

MAX_PREP_QUESTIONS = 10   # cap on prepare-for questions shown to the writer
MAX_CANDIDATES = 15       # cap on candidates judged by the question builder
PROFILE_WORD_CAP = 600    # student-profile budget in words


def _build_student_profile(already_covered: list, run_summaries: list) -> str:
    """One merged knowledge block: past-lecture snippets + this run's section summaries."""
    parts = []
    if already_covered:
        snippets = [a.get("summary_snippet", "") for a in already_covered if a.get("summary_snippet")]
        if snippets:
            parts.append("From earlier worksheets:\n- " + "\n- ".join(snippets))
    if run_summaries:
        parts.append("From earlier sections of this worksheet:\n- " + "\n- ".join(run_summaries))

    profile = "\n\n".join(parts)
    if not profile:
        return "The student has not covered any prior material."

    words = profile.split()
    if len(words) > PROFILE_WORD_CAP:
        # Keep the most recent knowledge (tail); drop the oldest overflow.
        profile = " ".join(words[-PROFILE_WORD_CAP:])
    return profile


def _question_text(q) -> str:
    if isinstance(q, dict):
        return q.get("text") or q.get("question") or ""
    return str(q or "")


def _build_candidates(section_idx: int, section: dict, memory_questions: list, deferred: list, seen_keys: set):
    """
    Flatten PYQs, lecture-embedded questions and carried deferred items into one
    candidate list with stable ids. PYQs come first (primary material), then
    deferred rescues, then lecture questions.

    Returns (candidates, kb_by_id). seen_keys dedupes by (source, qid) within
    the run so two similar sections cannot both claim the same PYQ.
    """
    candidates = []
    kb_by_id = {}

    for mq in memory_questions:
        canonical = mq.get("canonical_topic", "")
        for m in mq.get("matches", []):
            key = (m.get("source"), str(m.get("qid")))
            if key in seen_keys:
                continue
            cid = f"kb:{m.get('pk')}"
            if cid in kb_by_id:
                continue
            entry = {
                "id": cid,
                "kind": "pyq",
                "text": m.get("question", ""),
                "source": m.get("source") or canonical,
                "answer": m.get("answer", ""),
                "options": m.get("options"),
                "topic": canonical,
                "repeat": bool(m.get("repeat", False)),
            }
            candidates.append(entry)
            kb_by_id[cid] = {"pk": m.get("pk"), "exam": m.get("source"), "qid": m.get("qid")}

    for d in deferred:
        candidates.append({
            "id": d.get("id") or f"def:{section_idx}:{len(candidates)}",
            "kind": "deferred",
            "text": d.get("text", ""),
            "source": d.get("source", ""),
            "answer": d.get("answer", ""),
            "options": None,
        })

    for j, q in enumerate(section.get("extracted_questions", []) or []):
        candidates.append({
            "id": f"lec:{section_idx}:{j}",
            "kind": "lecture",
            "text": _question_text(q),
            "source": "lecture slide",
            "answer": "",
            "options": None,
        })

    return candidates[:MAX_CANDIDATES], kb_by_id


def run_generation_pipeline(
    pedagogical_json: list,
    kb,
    lecture_id: str,
    output_path: Path,
    cache: PipelineCache,
    update_memory: bool = True,
    is_objective: bool = False,
    newpage_per_question: bool = True,
    reuse: str = "prefer",
) -> dict:
    """
    Two LLM calls per section: the Section Writer (theory, notation, summary)
    and the Question Set Builder (practice ladder + PYQ curation + deferral).
    Everything else — rolling context, worksheet assembly, memory commits — is
    deterministic. Writes the worksheet JSON (docs/WORKSHEET_JSON_SCHEMA.md) to
    output_path; formatting (LaTeX etc.) is a separate step.
    """
    if isinstance(pedagogical_json, dict):
        pedagogical_json = pedagogical_json.get("section_map", [])

    worksheet_sections = []
    run_summaries: list[str] = []
    deferred_questions: list = []
    seen_keys: set = set()
    total_sections = len(pedagogical_json)

    for i, section in enumerate(pedagogical_json):
        section_title = section.get("section_title", f"Section {i + 1}")
        section_content = section.get("section_content", "")

        log.info("--- Processing Section %d/%d: %s ---", i + 1, total_sections, section_title)

        topics = section.get("topics", [])
        subtopics = section.get("subtopics", [])

        # ----- Memory query -----
        if kb:
            memory_results = kb.query(topics=topics + subtopics, lecture_id=lecture_id, reuse=reuse)
            memory_questions = memory_results.get("questions", [])
            book_context = memory_results.get("book_context", [])
            already_covered = memory_results.get("already_covered", [])
        else:
            memory_questions, book_context, already_covered = [], [], []

        candidates, kb_by_id = _build_candidates(i, section, memory_questions, deferred_questions, seen_keys)

        # ----- Call A: Section Writer -----
        writer_cached = cache.get_section_step(i, "writer")
        if writer_cached:
            log.info("  Theory cached")
            writer_output = WriterOutput.model_validate_json(writer_cached)
        else:
            # Safeguarded prepare-for list: question text + topic only —
            # answers/options stripped so they cannot leak into the theory.
            prep_questions = [
                {"source": c["source"], "topic": c.get("topic", ""), "question": c["text"]}
                for c in candidates if c["kind"] in ("pyq", "deferred")
            ][:MAX_PREP_QUESTIONS]

            writer_output = write_section(
                section_content=section_content,
                book_context=book_context,
                student_profile=_build_student_profile(already_covered, run_summaries),
                prep_questions=prep_questions,
                learning_objectives=section.get("learning_objectives", []),
                key_misconceptions=section.get("key_misconceptions", []),
            )
            cache.set_section_step(i, "writer", writer_output.model_dump_json())

        # ----- Call B: Question Set Builder -----
        questions_cached = cache.get_section_step(i, "questions")
        if questions_cached:
            log.info("  Question set cached")
            question_set = QuestionSet.model_validate_json(questions_cached)
        else:
            question_set = build_question_set(
                section_theory=theory_as_text(writer_output.theory),
                candidates=candidates,
                student_profile=_build_student_profile(already_covered, run_summaries),
                is_objective=is_objective,
            )
            cache.set_section_step(i, "questions", question_set.model_dump_json())

        # Bookkeeping: included PYQs are consumed for the rest of this run.
        included_pyqs = [p for p in question_set.pyq if p.id and p.id.startswith("kb:")]
        for p in included_pyqs:
            info = kb_by_id.get(p.id)
            if info:
                seen_keys.add((info.get("exam"), str(info.get("qid"))))
        deferred_questions = [d.model_dump() for d in question_set.deferred]

        # ----- Deterministic assembly (content only, no formatting) -----
        worksheet_section = build_section(i + 1, section, writer_output, question_set)
        worksheet_sections.append(worksheet_section)

        # ----- Rolling context: deterministic append of writer summaries -----
        run_summaries.append(writer_output.summary)

        # ----- Memory commit -----
        if kb and update_memory:
            if cache.get_section_step(i, "memory_updated"):
                log.info("  Memory update already committed")
            else:
                log.info("  Updating memory store...")
                kb.update(
                    lecture_id=lecture_id,
                    section_json=section,
                    summary=writer_output.summary,
                    # The KB column is named "latex"; it now stores the
                    # section's worksheet JSON (nothing reads it back).
                    latex=worksheet_section.model_dump_json(),
                    topics=topics + subtopics,
                )
                if included_pyqs:
                    kb.mark_questions_used(
                        [
                            {
                                "pk": kb_by_id[p.id]["pk"],
                                "exam": kb_by_id[p.id]["exam"],
                                "qid": kb_by_id[p.id]["qid"],
                                "action": "adapted" if p.adapted else "included",
                            }
                            for p in included_pyqs if p.id in kb_by_id
                        ],
                        lecture_id=lecture_id,
                    )
                cache.set_section_step(i, "memory_updated", True)

    if deferred_questions:
        log.warning("Questions deferred by every section (still unused in memory, will resurface next run):")
        for d in deferred_questions:
            log.warning("  - [%s] %s — reason: %s", d.get("source", "?"), d.get("text", "")[:100], d.get("reason", ""))

    # =================================================================
    # STAGE 3: WORKSHEET JSON (formatting is a separate step)
    # =================================================================
    module_name = output_path.name.split(".")[0].replace("_", " ").replace("-", " ").title()
    worksheet = build_worksheet(
        title=module_name,
        lecture_id=lecture_id,
        sections=worksheet_sections,
        unplaced=deferred_questions,
        is_objective=is_objective,
        newpage_per_question=newpage_per_question,
    )
    worksheet_json = worksheet.model_dump_json(indent=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(worksheet_json + "\n")

    log.info("Generation complete! Worksheet JSON saved to: %s", output_path)
    return {"worksheet": json.loads(worksheet_json), "summaries": run_summaries}
