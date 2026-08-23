import json
import uuid
import faiss
import numpy as np
from .topics import resolve_topics, add_new_cluster
from .llm import ollama_embed

def ingest_section(db_manager, lecture_id: str, section_json: dict, summary: str, latex: str, topics: list[str]) -> str:
    conn = db_manager.conn

    # 1. Resolve topics
    resolved = resolve_topics(db_manager, topics)
    
    final_cluster_ids = set()
    for topic_str, cluster_ids in resolved.items():
        if cluster_ids:
            for cid in cluster_ids:
                final_cluster_ids.add(cid)
        else:
            new_cid = add_new_cluster(db_manager, topic_str, source="lecture")
            final_cluster_ids.add(new_cid)

    # 2. Insert new sections row
    section_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sections (section_id, lecture_id, latex, summary, source_json) VALUES (?, ?, ?, ?, ?)",
        (section_id, lecture_id, latex, summary, json.dumps(section_json))
    )

    # 3. Insert section_topics rows
    for cid in final_cluster_ids:
        conn.execute(
            "INSERT INTO section_topics (section_id, cluster_id) VALUES (?, ?)",
            (section_id, cid)
        )

    # 4. Upsert lecture_topics rows marking confirmed
    for cid in final_cluster_ids:
        conn.execute(
            """INSERT INTO lecture_topics (lecture_id, cluster_id, status)
               VALUES (?, ?, 'confirmed')
               ON CONFLICT(lecture_id, cluster_id) DO UPDATE SET status='confirmed'""",
            (lecture_id, cid)
        )
    conn.commit()

    # 5. Embed summary and add to FAISS
    index, meta_json = db_manager.load_faiss_index("summaries")
    summaries_meta = json.loads(meta_json) if meta_json else []

    vec = ollama_embed(summary)
    summaries_meta.append({
        "section_id": section_id,
        "lecture_id": lecture_id,
        "cluster_ids": list(final_cluster_ids),
        "summary": summary
    })

    mat = np.array([vec], dtype="float32")
    faiss.normalize_L2(mat)
    if index is None:
        index = faiss.IndexFlatIP(len(vec))
    index.add(mat)
    db_manager.save_faiss_index("summaries", index, json.dumps(summaries_meta))

    print(f"Ingested section {section_id} for lecture {lecture_id}")
    return section_id
