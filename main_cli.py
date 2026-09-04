import argparse
import json
import logging
import sys
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

    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
    gen_p.add_argument("--out", type=Path, required=True, help="Output .typ file path")
    gen_p.add_argument("--no-memory-update", action="store_true", help="Skip updating memory store")
    gen_p.add_argument("--objective", action="store_true", help="Generate MCQs")
    gen_p.add_argument("--no-newpage", action="store_true", help="Skip newpage per question")
    gen_p.add_argument("--no-reuse", action="store_true", help="Never serve PYQs already used in a previous worksheet")
    gen_p.add_argument("--fresh", action="store_true", help="Ignore any cached pipeline progress")

    # run command
    run_p = subparsers.add_parser("run")
    run_p.add_argument("pdf_file", type=Path, help="Path to the lecture PDF")
    run_p.add_argument("--kb", type=Path, help="Path to CMKB store (optional)")
    run_p.add_argument("--lecture-id", help="Lecture ID for memory context (optional)")
    run_p.add_argument("--out", type=Path, required=True, help="Output .typ file path")
    run_p.add_argument("--no-memory-update", action="store_true", help="Skip updating memory store")
    run_p.add_argument("--objective", action="store_true", help="Generate MCQs")
    run_p.add_argument("--no-newpage", action="store_true", help="Skip newpage per question")
    run_p.add_argument("--no-reuse", action="store_true", help="Never serve PYQs already used in a previous worksheet")
    run_p.add_argument("--fresh", action="store_true", help="Ignore any cached pipeline progress")

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
            lecture_id=args.lecture_id,
            fresh=args.fresh,
        )

        run_generation_pipeline(
            pedagogical_json=pedagogical_json,
            kb=kb,
            lecture_id=args.lecture_id,
            output_typ_path=args.out,
            cache=cache,
            update_memory=not args.no_memory_update,
            is_objective=args.objective,
            newpage_per_question=not args.no_newpage,
            reuse="never" if args.no_reuse else "prefer",
        )

    elif args.command == "run":
        # One shared cache for extract + generate
        cache = PipelineCache(
            args.pdf_file,
            kb_id=str(args.kb) if args.kb else None,
            lecture_id=args.lecture_id,
            fresh=args.fresh,
        )

        extraction_data = run_extraction_pipeline(
            pdf_path=args.pdf_file,
            output_json_path=args.out.with_suffix('.json'),
            cache=cache,
        )

        kb = KnowledgeBase.load(str(args.kb)) if args.kb else None

        run_generation_pipeline(
            pedagogical_json=extraction_data,
            kb=kb,
            lecture_id=args.lecture_id,
            output_typ_path=args.out,
            cache=cache,
            update_memory=not args.no_memory_update,
            is_objective=args.objective,
            newpage_per_question=not args.no_newpage,
            reuse="never" if args.no_reuse else "prefer",
        )


if __name__ == "__main__":
    main()
