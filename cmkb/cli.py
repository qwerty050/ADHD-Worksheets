import argparse
import sys
import json
from .kb import KnowledgeBase

def main():
    parser = argparse.ArgumentParser(description="CMKB CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create")
    create_p.add_argument("path")
    create_p.add_argument("--name", required=True)
    create_p.add_argument("--pdf-mode", choices=["chunking", "page_index"], default="chunking")
    create_p.add_argument("--embed-model", default="nomic-embed-text")
    create_p.add_argument("--embed-dim", type=int, default=768)

    # ingest
    ingest_p = subparsers.add_parser("ingest")
    ingest_subs = ingest_p.add_subparsers(dest="ingest_type", required=True)

    ing_q = ingest_subs.add_parser("questions")
    ing_q.add_argument("path")
    ing_q.add_argument("json_file")

    ing_p = ingest_subs.add_parser("pdf")
    ing_p.add_argument("path")
    ing_p.add_argument("pdf_file")
    ing_p.add_argument("--mode", choices=["chunking", "page_index"])

    ing_l = ingest_subs.add_parser("lecture")
    ing_l.add_argument("path")
    ing_l.add_argument("json_file")
    ing_l.add_argument("--lecture-id", required=True)

    ing_s = ingest_subs.add_parser("section")
    ing_s.add_argument("path")
    ing_s.add_argument("--section-json", required=True)
    ing_s.add_argument("--summary", required=True)
    ing_s.add_argument("--latex", required=True)
    ing_s.add_argument("--lecture-id", required=True)
    ing_s.add_argument("--topics", required=True)

    # query
    query_p = subparsers.add_parser("query")
    query_p.add_argument("path")
    query_p.add_argument("--topics", required=True)
    query_p.add_argument("--lecture-id")
    query_p.add_argument("-k", type=int, default=8)

    # cluster
    cluster_p = subparsers.add_parser("cluster")
    cluster_p.add_argument("path")

    # inspect
    inspect_p = subparsers.add_parser("inspect")
    inspect_p.add_argument("path")
    inspect_p.add_argument("--lecture-id")

    # debug-topic
    debug_p = subparsers.add_parser("debug-topic")
    debug_p.add_argument("path")
    debug_p.add_argument("query")

    args = parser.parse_args()

    if args.command == "create":
        KnowledgeBase.create(args.path, args.name, args.pdf_mode, args.embed_model, args.embed_dim)
        print(f"Created KB at {args.path}")

    elif args.command == "ingest":
        kb = KnowledgeBase.load(args.path)
        if args.ingest_type == "questions":
            kb.ingest_questions(args.json_file)
        elif args.ingest_type == "pdf":
            kb.ingest_pdf(args.pdf_file, args.mode)
        elif args.ingest_type == "lecture":
            kb.ingest_lecture(args.json_file, args.lecture_id)
        elif args.ingest_type == "section":
            with open(args.section_json) as f:
                s_json = json.load(f)
            with open(args.summary) as f:
                summ = f.read()
            with open(args.latex) as f:
                lat = f.read()
            topics = [t.strip() for t in args.topics.split(",")]
            sid = kb.ingest_section(s_json, summ, lat, args.lecture_id, topics)
            print(sid)

    elif args.command == "query":
        kb = KnowledgeBase.load(args.path)
        topics = [t.strip() for t in args.topics.split(",")]
        res = kb.query(topics, args.lecture_id, args.k)
        print(json.dumps(res, indent=2))

    elif args.command == "cluster":
        kb = KnowledgeBase.load(args.path)
        kb.cluster()
        
    elif args.command == "inspect":
        kb = KnowledgeBase.load(args.path)
        # minimal stub for inspect
        rows = kb.db.conn.execute("SELECT cluster_id, canonical_name, member_count, source FROM topic_clusters").fetchall()
        print("--- Topics ---")
        for r in rows:
            print(f"[{r['cluster_id']}] {r['canonical_name']} (source: {r['source']}, members: {r['member_count']})")
            
    elif args.command == "debug-topic":
        from .topics import resolve_topics, _lexical_match_clusters, _nearest_topic_clusters
        kb = KnowledgeBase.load(args.path)
        index, meta_json = kb.db.load_faiss_index("topics")
        if not index:
            print("No topics found.")
            return
        topic_meta = json.loads(meta_json)
        
        lex_hits = _lexical_match_clusters(args.query, topic_meta)
        if lex_hits:
            print(f"Exact matches for '{args.query}':")
            for cid, name, matched in lex_hits:
                print(f"  [{cid}] {name} (via '{matched}')")
        else:
            print(f"No exact matches for '{args.query}'.")
            
        near = _nearest_topic_clusters(args.query, index, topic_meta)
        print(f"\nNearest clusters by embedding:")
        for cid, name, matched, dist in near:
            print(f"  [{cid}] {name} (via '{matched}', dist {dist:.3f})")

if __name__ == "__main__":
    main()
