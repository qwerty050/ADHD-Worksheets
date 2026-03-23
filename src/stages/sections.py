"""
Stage 2 — Per-section processing (theory, questions, PYQs, compile, review,
           context update).
Stage 3 — Deterministic document formatting.
"""

import json
from pathlib import Path

from src.llm import MODELS, call_ollama
from src.cache import PipelineCache
from src.formatter import (
    compile_section,
    format_document,
    generate_context_summary,
)
from src.prompts import (
    SYSTEM_PROMPT_SECTION_THEORY,
    SYSTEM_PROMPT_SECTION_QUESTIONS_HOTS,
    SYSTEM_PROMPT_SECTION_QUESTIONS_PYQ,
    SYSTEM_PROMPT_CONTEXT_SUMMARIZER,
    SYSTEM_PROMPT_REVIEW,
)


def process_all_sections(
    enriched_section_map: list,
    extracted_pyqs: list,
    cache: PipelineCache,
    target_json: Path,
    is_objective: bool = False,
    review: bool = True,
    newpage_per_question: bool = True,
) -> dict:
    """
    Run Stages 2 and 3: per-section content generation followed by
    deterministic document formatting.

    Returns:
        dict with keys "latex" and "context".
    """
    compiled_sections = []
    section_titles = []
    section_topics_list = []
    notation_data_list = []
    total_sections = len(enriched_section_map)
    rolling_context = ""
    deferred_pyqs: list = []

    for i, section in enumerate(enriched_section_map):
        section_title = section.get("section_title", f"Section {i + 1}")
        section_raw_content = section.get("section_content", "")
        section_metadata = {
            k: v
            for k, v in section.items()
            if k
            not in (
                "section_title",
                "section_content",
                "topics",
                "subtopics",
                "dependency_order",
            )
        }

        print(
            f"\n--- Processing Section {i + 1}/{total_sections}: "
            f"{section_title} ---"
        )

        # ----- Step 2.1: Theory Generation -----
        section_theory = cache.get_section_step(i, "theory")
        if section_theory:
            print("  Theory cached ✓")
        else:
            print("  Generating Theory...")
            theory_prompt = f"SECTION RAW CONTENT:\n{section_raw_content}"
            theory_prompt += (
                f"\n\nPEDAGOGICAL METADATA:\n"
                f"{json.dumps(section_metadata, indent=2)}"
            )
            if rolling_context:
                theory_prompt += (
                    f"\n\nPREVIOUS SECTIONS CONTEXT:\n{rolling_context}"
                )

            section_theory = call_ollama(
                model=MODELS["pro"],
                prompt=theory_prompt,
                system=SYSTEM_PROMPT_SECTION_THEORY,
            )
            cache.set_section_step(i, "theory", section_theory)

        # ----- Step 2.2: HOTS Questions -----
        hots_questions = cache.get_section_step(i, "hots")
        if hots_questions:
            print("  HOTS Questions cached ✓")
            # Ensure cached value is a list (old caches may store raw text)
            if isinstance(hots_questions, str):
                try:
                    parsed = json.loads(hots_questions)
                    hots_questions = parsed.get(
                        "questions",
                        [parsed] if isinstance(parsed, str) else [],
                    )
                except json.JSONDecodeError:
                    hots_questions = [hots_questions]
        else:
            print("  Generating HOTS Questions...")
            question_prompts = section.get("question_prompts", {})
            hots_prompt = (
                f"SECTION RAW CONTENT:\n{section_raw_content}\n\n"
                f"SECTION THEORY:\n{section_theory}\n\n"
                f"QUESTION PROMPTS FROM METADATA:\n"
                f"{json.dumps(question_prompts, indent=2)}\n\n"
                f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}\n\n"
                f"IS OBJECTIVE MODE: {is_objective}"
            )
            hots_response = call_ollama(
                model=MODELS["pro"],
                prompt=hots_prompt,
                system=SYSTEM_PROMPT_SECTION_QUESTIONS_HOTS,
                as_json=True,
            )
            try:
                hots_parsed = json.loads(hots_response)
                hots_questions = hots_parsed.get("questions", [])
            except json.JSONDecodeError:
                print("  Warning: Failed to parse HOTS JSON. Storing as single question.")
                hots_questions = [hots_response]
            cache.set_section_step(i, "hots", hots_questions)

        # ----- Step 2.3: PYQ Filter + Adaptation -----
        pyq_questions = cache.get_section_step(i, "pyq")
        if pyq_questions:
            print("  PYQs cached ✓")
            if isinstance(pyq_questions, str):
                try:
                    parsed = json.loads(pyq_questions)
                    pyq_questions = parsed.get("questions", [])
                except json.JSONDecodeError:
                    pyq_questions = (
                        [pyq_questions]
                        if pyq_questions.strip()
                        and not pyq_questions.startswith("% No PYQs")
                        else []
                    )
            cached_deferred = cache.get_section_step(i, "deferred_pyqs")
            if cached_deferred:
                deferred_pyqs = (
                    json.loads(cached_deferred)
                    if isinstance(cached_deferred, str)
                    else cached_deferred
                )
        else:
            print("  Filtering & adapting PYQs...")

            section_pyqs = [
                q
                for q in extracted_pyqs
                if section_title in q.get("mapped_sections", [])
            ]
            section_pyqs.extend(deferred_pyqs)

            if section_pyqs:
                pyq_prompt = (
                    f"SECTION RAW CONTENT:\n{section_raw_content}\n\n"
                    f"PRE-MAPPED PYQ LIST FOR THIS SECTION:\n"
                    f"{json.dumps(section_pyqs, indent=2)}\n\n"
                    f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}\n\n"
                    f"IS OBJECTIVE MODE: {is_objective}"
                )
                pyq_response = call_ollama(
                    model=MODELS["flashLite"],
                    prompt=pyq_prompt,
                    system=SYSTEM_PROMPT_SECTION_QUESTIONS_PYQ,
                    as_json=True,
                )

                try:
                    pyq_parsed = json.loads(pyq_response)
                    pyq_questions = pyq_parsed.get("questions", [])
                    deferred_pyqs = pyq_parsed.get("deferred_pyqs", [])
                except json.JSONDecodeError:
                    print("  Warning: Failed to parse PYQ JSON. Storing as single question.")
                    pyq_questions = [pyq_response]
                    deferred_pyqs = []
            else:
                pyq_questions = []
                deferred_pyqs = []

            cache.set_section_step(i, "pyq", pyq_questions)
            cache.set_section_step(i, "deferred_pyqs", json.dumps(deferred_pyqs))

        # ----- Step 2.4: Compile (deterministic) -----
        compiled_text = cache.get_section_step(i, "compiled")
        if compiled_text:
            print("  Compiled module cached ✓")
        else:
            print("  Compiling Module (deterministic)...")
            compiled_text = compile_section(
                section_title=section_title,
                theory_text=section_theory,
                hots_questions=hots_questions,
                pyq_questions=pyq_questions,
                newpage_per_question=newpage_per_question,
            )
            cache.set_section_step(i, "compiled", compiled_text)

        # ----- Step 2.6: Review Pass (optional) -----
        if review:
            review_result = cache.get_section_step(i, "review")
            if review_result:
                print("  Review cached ✓")
                if isinstance(review_result, str):
                    try:
                        review_result = json.loads(review_result)
                    except json.JSONDecodeError:
                        review_result = {
                            "status": "pass",
                            "flags": [],
                            "summary": "Cached (unparseable).",
                        }
            else:
                print("  Running Review Pass...")
                review_prompt = (
                    f"COMPILED SECTION LATEX:\n{compiled_text}\n\n"
                    f"PEDAGOGICAL METADATA:\n"
                    f"{json.dumps(section_metadata, indent=2)}\n\n"
                    f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}"
                )
                review_response = call_ollama(
                    model=MODELS["flash"],
                    prompt=review_prompt,
                    system=SYSTEM_PROMPT_REVIEW,
                    as_json=True,
                )

                try:
                    review_result = json.loads(review_response)
                except json.JSONDecodeError:
                    review_result = {
                        "status": "pass",
                        "flags": [],
                        "summary": "Review parse failed.",
                    }

                cache.set_section_step(i, "review", review_result)

            # Log review results
            status = review_result.get("status", "pass")
            flags = review_result.get("flags", [])
            summary = review_result.get("summary", "")

            if status == "flag":
                print(f"  ⚠ Review FLAGGED: {summary}")
                for flag in flags:
                    print(
                        f"    - [{flag.get('type', '?')}] "
                        f"{flag.get('suggestion', flag.get('term', flag.get('missing_level', '')))}"
                    )

                critical_types = {"undefined_term", "knowledge_assumption"}
                critical_flags = [
                    f for f in flags if f.get("type") in critical_types
                ]
                if critical_flags:
                    banner_lines = [
                        f"% !!!  REVIEW FLAG: {section_title}  !!!",
                    ]
                    for cf in critical_flags:
                        banner_lines.append(
                            f"% [{cf.get('type')}] "
                            f"{cf.get('suggestion', cf.get('term', ''))}"
                        )
                    banner_lines.append("% !!! END REVIEW FLAGS !!!")
                    compiled_text = "\n".join(banner_lines) + "\n" + compiled_text
            else:
                print(f"  ✓ Review passed: {summary}")

        compiled_sections.append(compiled_text)
        section_titles.append(section_title)
        section_topics_list.append(section.get("topics", []))
        notation_data_list.append(section.get("notation_introduced", []))

        # ----- Step 2.5: Update Rolling Context -----
        new_section_info = (
            f"Section: {section_title}, "
            f"Topics: {', '.join(section.get('topics', []))}"
        )
        cached_context = cache.get_section_step(i, "context")
        if cached_context:
            print("  Rolling Context updated natively ✓")
            rolling_context = cached_context
        else:
            print("  Updating Rolling Context via LLM summarisation...")
            context_prompt = (
                f"CURRENT ROLLING CONTEXT:\n{rolling_context}\n\n"
                f"NEWLY ADDED SECTION:\n{new_section_info}"
            )
            rolling_context = call_ollama(
                model=MODELS["flashLite"],
                prompt=context_prompt,
                system=SYSTEM_PROMPT_CONTEXT_SUMMARIZER,
            )
            cache.set_section_step(i, "context", rolling_context)

    # =================================================================
    # STAGE 3: DETERMINISTIC FORMATTING
    # =================================================================
    print("\nStage 3: Formatting Document (deterministic)...")

    module_name = target_json.stem.replace("_", " ").replace("-", " ").title()
    metadata = {
        "title": f"Learning Module: {module_name}",
        "author": "",
        "date": r"\today",
    }

    latex = format_document(
        compiled_sections, section_titles, metadata,
        notation_data=notation_data_list,
    )
    context = generate_context_summary(section_titles, section_topics_list)

    print("\nDone! Pipeline finished successfully.")
    return {"latex": latex, "context": context}
