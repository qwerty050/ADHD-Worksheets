import json
from .topics import resolve_topics, add_new_cluster

def ingest_lecture(db_manager, json_path: str, lecture_id: str):
    with open(json_path, "r") as f:
        data = json.load(f)

    # Extract topics from section_map
    lecture_topics = set()
    for section in data.get("section_map", []):
        for topic in section.get("topics", []):
            lecture_topics.add(topic)

    topics_list = list(lecture_topics)
    if not topics_list:
        print(f"No topics found for lecture {lecture_id}")
        return

    resolved = resolve_topics(db_manager, topics_list)
    
    conn = db_manager.conn
    
    for topic_str, cluster_ids in resolved.items():
        if cluster_ids:
            # Confirmed match
            for cid in cluster_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO lecture_topics (lecture_id, cluster_id, status) VALUES (?, ?, ?)",
                    (lecture_id, cid, "confirmed")
                )
        else:
            # New cluster on the fly
            new_cid = add_new_cluster(db_manager, topic_str, source="lecture")
            conn.execute(
                "INSERT OR IGNORE INTO lecture_topics (lecture_id, cluster_id, status) VALUES (?, ?, ?)",
                (lecture_id, new_cid, "new")
            )
            print(f"Created new lecture-sourced cluster for: {topic_str}")

    conn.commit()
    print(f"Ingested lecture {lecture_id} with {len(topics_list)} unique topics.")
