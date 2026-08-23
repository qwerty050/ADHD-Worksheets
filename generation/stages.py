import json
from shared.llm import get_llm_client
from shared.config import (
    MODEL_THEORY,
    MODEL_QUESTIONS,
    MODEL_QUESTION_FILTER,
    MODEL_REVIEW,
    MODEL_CONTEXT_SUMMARY,
)
from generation.prompts import (
    SYSTEM_PROMPT_SECTION_THEORY,
    SYSTEM_PROMPT_SECTION_QUESTIONS_HOTS,
    SYSTEM_PROMPT_SECTION_QUESTIONS_EXTRACTED,
    SYSTEM_PROMPT_CONTEXT_SUMMARIZER,
    SYSTEM_PROMPT_REVIEW,
)


def generate_theory(
    section_raw_content: str,
    section_metadata: dict,
    rolling_context: str,
    book_context: list,
    already_covered: list,
) -> str:
    print("  Generating Theory...")
    theory_prompt = f"SECTION RAW CONTENT:\n{section_raw_content}\n\n"
    
    if book_context:
        theory_prompt += f"BOOK CONTEXT:\n{json.dumps(book_context, indent=2)}\n\n"
        
    theory_prompt += f"PEDAGOGICAL METADATA:\n{json.dumps(section_metadata, indent=2)}\n\n"
    
    if rolling_context:
        theory_prompt += f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}\n\n"
        
    if already_covered:
        theory_prompt += f"ALREADY COVERED:\n{json.dumps(already_covered, indent=2)}\n\n"

    section_theory = get_llm_client().generate(
        prompt=theory_prompt,
        model_name=MODEL_THEORY,
        system=SYSTEM_PROMPT_SECTION_THEORY,
    )
    return section_theory


def generate_questions_hots(
    section_raw_content: str,
    section_theory: str,
    question_prompts: dict,
    rolling_context: str,
    is_objective: bool,
) -> list:
    print("  Generating HOTS Questions...")
    hots_prompt = (
        f"SECTION RAW CONTENT:\n{section_raw_content}\n\n"
        f"SECTION THEORY:\n{section_theory}\n\n"
        f"QUESTION PROMPTS FROM METADATA:\n"
        f"{json.dumps(question_prompts, indent=2)}\n\n"
        f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}\n\n"
        f"IS OBJECTIVE MODE: {is_objective}"
    )
    hots_response = get_llm_client().generate(
        prompt=hots_prompt,
        model_name=MODEL_QUESTIONS,
        system=SYSTEM_PROMPT_SECTION_QUESTIONS_HOTS,
        as_json=True,
    )
    try:
        hots_parsed = json.loads(hots_response)
        return hots_parsed.get("questions", [])
    except json.JSONDecodeError:
        print("  Warning: Failed to parse HOTS JSON. Storing as single question.")
        return [hots_response]


def filter_extracted_questions(
    section_raw_content: str,
    section_questions: list,
    rolling_context: str,
    is_objective: bool,
) -> tuple[list, list]:
    print("  Filtering & adapting extracted questions...")
    
    if not section_questions:
        return [], []

    extracted_prompt = (
        f"SECTION RAW CONTENT:\n{section_raw_content}\n\n"
        f"PRE-MAPPED QUESTIONS LIST FOR THIS SECTION:\n"
        f"{json.dumps(section_questions, indent=2)}\n\n"
        f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}\n\n"
        f"IS OBJECTIVE MODE: {is_objective}"
    )
    extracted_response = get_llm_client().generate(
        prompt=extracted_prompt,
        model_name=MODEL_QUESTION_FILTER,
        system=SYSTEM_PROMPT_SECTION_QUESTIONS_EXTRACTED,
        as_json=True,
    )

    try:
        extracted_parsed = json.loads(extracted_response)
        questions_list = extracted_parsed.get("questions", [])
        deferred_questions = extracted_parsed.get("deferred_questions", [])
        return questions_list, deferred_questions
    except json.JSONDecodeError:
        print("  Warning: Failed to parse Extracted Questions JSON.")
        return [extracted_response], []


def review_section(
    compiled_text: str,
    section_metadata: dict,
    rolling_context: str,
) -> dict:
    print("  Running Review Pass...")
    review_prompt = (
        f"COMPILED SECTION LATEX:\n{compiled_text}\n\n"
        f"PEDAGOGICAL METADATA:\n"
        f"{json.dumps(section_metadata, indent=2)}\n\n"
        f"PREVIOUS SECTIONS CONTEXT:\n{rolling_context}"
    )
    review_response = get_llm_client().generate(
        prompt=review_prompt,
        model_name=MODEL_REVIEW,
        system=SYSTEM_PROMPT_REVIEW,
        as_json=True,
    )

    try:
        return json.loads(review_response)
    except json.JSONDecodeError:
        return {
            "status": "pass",
            "flags": [],
            "summary": "Review parse failed.",
        }


def generate_context_summary(
    rolling_context: str,
    section_title: str,
    section_topics: list,
) -> str:
    print("  Updating Rolling Context via LLM summarisation...")
    new_section_info = f"Section: {section_title}, Topics: {', '.join(section_topics)}"
    context_prompt = (
        f"CURRENT ROLLING CONTEXT:\n{rolling_context}\n\n"
        f"NEWLY ADDED SECTION:\n{new_section_info}"
    )
    return get_llm_client().generate(
        prompt=context_prompt,
        model_name=MODEL_CONTEXT_SUMMARY,
        system=SYSTEM_PROMPT_CONTEXT_SUMMARIZER,
    )
