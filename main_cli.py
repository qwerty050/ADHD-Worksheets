import argparse
import sys
import json
from pathlib import Path

from extraction.pipeline import run_extraction_pipeline
from generation.pipeline import run_generation_pipeline
from shared.cache import PipelineCache
from cmkb.kb import KnowledgeBase

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "memory":
        # Pass through to cmkb CLI
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from cmkb.cli import main as cmkb_main
        cmkb_main()
        return

    parser = argparse.ArgumentParser(description="ADHD Worksheets Generator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract command
    extract_p = subparsers.add_parser("extract")
    extract_p.add_argument("pdf_file", type=Path, help="Path to the lecture PDF")
    extract_p.add_argument("--out", type=Path, required=True, help="Output JSON path")

    # generate command
    gen_p = subparsers.add_parser("generate")
    gen_p.add_argument("json_file", type=Path, help="Pedagogical JSON from extract")
    gen_p.add_argument("--kb", type=Path, help="Path to CMKB store (optional)")
    gen_p.add_argument("--lecture-id", help="Lecture ID for memory context (optional)")
    gen_p.add_argument("--out", type=Path, required=True, help="Output .tex file path")
    gen_p.add_argument("--no-memory-update", action="store_true", help="Skip updating memory store")
    gen_p.add_argument("--objective", action="store_true", help="Generate MCQs")
    gen_p.add_argument("--no-review", action="store_true", help="Skip the LLM review pass")
    gen_p.add_argument("--no-newpage", action="store_true", help="Skip newpage per question")

    # run command
    run_p = subparsers.add_parser("run")
    run_p.add_argument("pdf_file", type=Path, help="Path to the lecture PDF")
    run_p.add_argument("--kb", type=Path, help="Path to CMKB store (optional)")
    run_p.add_argument("--lecture-id", help="Lecture ID for memory context (optional)")
    run_p.add_argument("--out", type=Path, required=True, help="Output .tex file path")
    run_p.add_argument("--no-memory-update", action="store_true", help="Skip updating memory store")
    run_p.add_argument("--objective", action="store_true", help="Generate MCQs")
    run_p.add_argument("--no-review", action="store_true", help="Skip the LLM review pass")
    run_p.add_argument("--no-newpage", action="store_true", help="Skip newpage per question")

    args = parser.parse_args()

    if args.command == "extract":
        run_extraction_pipeline(args.pdf_file, args.out)

    elif args.command == "generate":
        with open(args.json_file, "r", encoding="utf-8") as f:
            pedagogical_json = json.load(f)

        kb = KnowledgeBase.load(str(args.kb)) if args.kb else None
        cache = PipelineCache(
            args.json_file, 
            kb_id=str(args.kb) if args.kb else None, 
            lecture_id=args.lecture_id
        )

        run_generation_pipeline(
            pedagogical_json=pedagogical_json,
            kb=kb,
            lecture_id=args.lecture_id,
            output_tex_path=args.out,
            cache=cache,
            update_memory=not args.no_memory_update,
            is_objective=args.objective,
            review=not args.no_review,
            newpage_per_question=not args.no_newpage,
        )

    elif args.command == "run":
        # Extract -> generate
        cache = PipelineCache(
            args.pdf_file, 
            kb_id=str(args.kb) if args.kb else None, 
            lecture_id=args.lecture_id
        )
        
        extraction_data = run_extraction_pipeline(
            pdf_path=args.pdf_file, 
            output_json_path=args.out.with_suffix('.json')
        )

        kb = KnowledgeBase.load(str(args.kb)) if args.kb else None
        
        run_generation_pipeline(
            pedagogical_json=extraction_data,
            kb=kb,
            lecture_id=args.lecture_id,
            output_tex_path=args.out,
            cache=cache,
            update_memory=not args.no_memory_update,
            is_objective=args.objective,
            review=not args.no_review,
            newpage_per_question=not args.no_newpage,
        )

if __name__ == "__main__":
    main()
