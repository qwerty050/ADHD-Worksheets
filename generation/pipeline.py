import json
from pathlib import Path

from shared.cache import PipelineCache
from compiler.formatter import compile_section, format_document
from generation.stages import (
    generate_theory,
    generate_questions_hots,
    filter_extracted_questions,
    review_section,
    generate_context_summary,
    generate_section_summary,
)


def run_generation_pipeline(
    pedagogical_json: list,
    kb,
    lecture_id: str,
    output_tex_path: Path,
    cache: PipelineCache,
    update_memory: bool = True,
    is_objective: bool = False,
    review: bool = True,
    newpage_per_question: bool = True,
) -> dict:
    """
    Run Stages 2 and 3: per-section content generation with memory integration,
    followed by deterministic document formatting.
    """
    if isinstance(pedagogical_json, dict):
        pedagogical_json = pedagogical_json.get("section_map", [])

    compiled_sections = []
    section_titles = []
    section_topics_list = []
    notation_data_list = []
    total_sections = len(pedagogical_json)
    rolling_context = ""
    deferred_questions: list = []

    for i, section in enumerate(pedagogical_json):
        section_title = section.get("section_title", f"Section {i + 1}")
        section_raw_content = section.get("section_content", "")
        
        # Everything else goes to metadata
        section_metadata = {
            k: v for k, v in section.items()
            if k not in (
                "section_title", "section_content", "topics", "subtopics", "dependency_order"
            )
        }

        topics = section.get("topics", [])
        subtopics = section.get("subtopics", [])
        
        print(f"\n--- Processing Section {i + 1}/{total_sections}: {section_title} ---")

        # Memory Query Hook
        if kb:
            # Query memory before generation
            memory_results = kb.query(topics=topics + subtopics, lecture_id=lecture_id, k=5)
            memory_questions = memory_results.get("questions", [])
            book_context = memory_results.get("book_context", [])
            already_covered = memory_results.get("already_covered", [])
        else:
            memory_questions = []
            book_context = []
            already_covered = []

        # ----- Step 2.1: Theory Generation -----
        section_theory = cache.get_section_step(i, "theory")
        if section_theory:
            print("  Theory cached ✓")
        else:
            section_theory = generate_theory(
                section_raw_content=section_raw_content,
                section_metadata=section_metadata,
                rolling_context=rolling_context,
                book_context=book_context,
                already_covered=already_covered,
            )
            cache.set_section_step(i, "theory", section_theory)

        # ----- Step 2.2: HOTS Questions -----
        hots_questions = cache.get_section_step(i, "hots")
        if hots_questions:
            print("  HOTS Questions cached ✓")
            if isinstance(hots_questions, str):
                try:
                    parsed = json.loads(hots_questions)
                    hots_questions = parsed.get("questions", [parsed] if isinstance(parsed, str) else [])
                except json.JSONDecodeError:
                    hots_questions = [hots_questions]
        else:
            question_prompts = section.get("question_prompts", {})
            hots_questions = generate_questions_hots(
                section_raw_content=section_raw_content,
                section_theory=section_theory,
                question_prompts=question_prompts,
                rolling_context=rolling_context,
                is_objective=is_objective,
            )
            cache.set_section_step(i, "hots", hots_questions)

        # ----- Step 2.3: Extracted Questions Filter + Adaptation -----
        extracted_questions_list = cache.get_section_step(i, "extracted_questions")
        if extracted_questions_list:
            print("  Extracted questions cached ✓")
            if isinstance(extracted_questions_list, str):
                try:
                    parsed = json.loads(extracted_questions_list)
                    extracted_questions_list = parsed.get("questions", [])
                except json.JSONDecodeError:
                    extracted_questions_list = (
                        [extracted_questions_list]
                        if extracted_questions_list.strip()
                        and not extracted_questions_list.startswith("% No Extracted")
                        else []
                    )
            cached_deferred = cache.get_section_step(i, "deferred_questions")
            if cached_deferred:
                deferred_questions = (
                    json.loads(cached_deferred)
                    if isinstance(cached_deferred, str)
                    else cached_deferred
                )
        else:
            # Merge lecture-internal questions with PYQs from memory
            lecture_internal_questions = section.get("extracted_questions", [])
            
            flat_memory_questions = []
            for mq in memory_questions:
                for match in mq.get("matches", []):
                    flat_memory_questions.append({
                        "text": match.get("question", ""),
                        "source": match.get("source", f"Memory ({mq.get('canonical_topic', 'Unknown')})"),
                        "answer": match.get("answer", ""),
                        "type": "PYQ",
                        "topic": mq.get("canonical_topic", ""),
                        "qid": match.get("qid", "")
                    })
                    
            merged_candidate_questions = lecture_internal_questions + flat_memory_questions
            merged_candidate_questions.extend(deferred_questions)

            extracted_questions_list, deferred_questions = filter_extracted_questions(
                section_raw_content=section_raw_content,
                section_questions=merged_candidate_questions,
                rolling_context=rolling_context,
                is_objective=is_objective,
            )
            cache.set_section_step(i, "extracted_questions", extracted_questions_list)
            cache.set_section_step(i, "deferred_questions", json.dumps(deferred_questions))

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
                extracted_questions=extracted_questions_list,
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
                        review_result = {"status": "pass", "flags": [], "summary": "Cached (unparseable)."}
            else:
                review_result = review_section(
                    compiled_text=compiled_text,
                    section_metadata=section_metadata,
                    rolling_context=rolling_context,
                )
                cache.set_section_step(i, "review", review_result)

            status = review_result.get("status", "pass")
            flags = review_result.get("flags", [])
            summary = review_result.get("summary", "")

            if status == "flag":
                print(f"  ⚠ Review FLAGGED: {summary}")
                for flag in flags:
                    print(f"    - [{flag.get('type', '?')}] {flag.get('suggestion', flag.get('term', flag.get('missing_level', '')))}")
                
                critical_types = {"undefined_term", "knowledge_assumption"}
                critical_flags = [f for f in flags if f.get("type") in critical_types]
                if critical_flags:
                    banner_lines = [f"% !!!  REVIEW FLAG: {section_title}  !!!"]
                    for cf in critical_flags:
                        banner_lines.append(f"% [{cf.get('type')}] {cf.get('suggestion', cf.get('term', ''))}")
                    banner_lines.append("% !!! END REVIEW FLAGS !!!")
                    compiled_text = "\n".join(banner_lines) + "\n" + compiled_text
            else:
                print(f"  ✓ Review passed: {summary}")

        compiled_sections.append(compiled_text)
        section_titles.append(section_title)
        section_topics_list.append(topics)
        notation_data_list.append(section.get("notation_introduced", []))

        # ----- Step 2.5: Update Rolling Context -----
        cached_context = cache.get_section_step(i, "context")
        if cached_context:
            print("  Rolling Context updated natively ✓")
            rolling_context = cached_context
        else:
            rolling_context = generate_context_summary(
                rolling_context=rolling_context,
                section_title=section_title,
                section_topics=topics,
            )
            cache.set_section_step(i, "context", rolling_context)

        # ----- Memory Update Hook -----
        if kb and update_memory:
            memory_updated = cache.get_section_step(i, "memory_updated")
            if memory_updated:
                print("  Memory update already committed ✓")
            else:
                print("  Updating memory store...")
                section_summary = cache.get_section_step(i, "section_summary")
                if not section_summary:
                    section_summary = generate_section_summary(
                        section_title=section_title,
                        section_raw_content=section_raw_content,
                        section_theory=section_theory,
                    )
                    cache.set_section_step(i, "section_summary", section_summary)
                    
                kb.update(
                    lecture_id=lecture_id,
                    section_json=section,
                    summary=section_summary,  # Use section specific summary instead of rolling_context
                    latex=compiled_text,
                    topics=topics + subtopics,
                )
                cache.set_section_step(i, "memory_updated", True)


    # =================================================================
    # STAGE 3: DETERMINISTIC FORMATTING
    # =================================================================
    print("\nStage 3: Formatting Document (deterministic)...")

    module_name = output_tex_path.stem.replace("_", " ").replace("-", " ").title()
    metadata = {
        "title": f"Learning Module: {module_name}",
        "author": "",
        "date": r"\today",
    }

    latex = format_document(
        compiled_sections, section_titles, metadata,
        notation_data=notation_data_list,
    )
    
    # Save final latex
    output_tex_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_tex_path, "w", encoding="utf-8") as f:
        f.write(latex)

    print(f"\nGeneration complete! LaTeX saved to: {output_tex_path}")
    return {"latex": latex, "context": rolling_context}
