import json
import re
import numpy as np
import faiss
from sklearn.cluster import AgglomerativeClustering
from collections import Counter
from .llm import ollama_embed, ollama_generate_json
from .config import CLUSTER_DISTANCE_THRESHOLD, TOPIC_MATCH_THRESHOLD

ALIAS_SYSTEM_PROMPT = """You will be given a list of canonical ML topic names, each with \
an id. For each topic, list up to 4 short alternative ways a student might search for it: \
common acronyms, abbreviations, or looser phrasings. Do not repeat the canonical name itself.

Example: canonical "Support Vector Machines (SVM)" -> aliases ["SVM", "support vector \
classifier", "max margin classifier"]

Output ONLY valid JSON, no commentary, matching this schema exactly:
[{"cluster_id": <id>, "aliases": ["<alias 1>", "<alias 2>", ...]}]
"""

def build_topic_clusters(db_manager):
    conn = db_manager.conn
    rows = conn.execute("SELECT DISTINCT raw_tag FROM question_tags").fetchall()
    raw_tags = [r[0] for r in rows]
    if not raw_tags:
        print("No tags found. Run `ingest questions` first.")
        return

    print(f"Embedding {len(raw_tags)} unique raw tags...")
    vectors = np.vstack([ollama_embed(t) for t in raw_tags]).astype("float32")
    faiss.normalize_L2(vectors)

    sims = vectors @ vectors.T
    dist = 1 - sims
    np.fill_diagonal(dist, 0)
    dist = np.clip(dist, 0, None)

    clustering = AgglomerativeClustering(
        metric="precomputed",
        linkage="average",
        distance_threshold=CLUSTER_DISTANCE_THRESHOLD,
        n_clusters=None,
    )
    labels = clustering.fit_predict(dist)

    conn.execute("DELETE FROM question_topics")
    conn.execute("DELETE FROM topic_clusters WHERE source = 'pyq'") 
    # Notice: we should probably delete all topic_clusters if rebuilding from scratch, 
    # but the prompt says to allow incremental growth. If building pyq taxonomy, it overrides pyq sources.
    # Let's clear all for full cluster rebuild, as per original script.
    conn.execute("DELETE FROM topic_clusters")
    conn.execute("DELETE FROM lecture_topics")
    conn.execute("DELETE FROM section_topics")
    conn.commit()

    freq = dict(conn.execute(
        "SELECT raw_tag, COUNT(*) FROM question_tags GROUP BY raw_tag"
    ).fetchall())

    cluster_ids_created = {}
    topic_vectors = []
    topic_meta = []

    for sklearn_label in sorted(set(labels)):
        member_tags = [raw_tags[i] for i in range(len(raw_tags)) if labels[i] == sklearn_label]
        canonical = max(member_tags, key=lambda t: (freq.get(t, 0), -len(t)))

        cur = conn.execute(
            "INSERT INTO topic_clusters (canonical_name, member_count, source) VALUES (?, ?, 'pyq')",
            (canonical, sum(freq.get(t, 0) for t in member_tags)),
        )
        cluster_id = cur.lastrowid
        cluster_ids_created[sklearn_label] = cluster_id

        placeholders = ",".join("?" * len(member_tags))
        q_pks = conn.execute(
            f"SELECT DISTINCT question_pk FROM question_tags WHERE raw_tag IN ({placeholders})",
            member_tags,
        ).fetchall()
        for (qpk,) in q_pks:
            conn.execute(
                "INSERT INTO question_topics (question_pk, cluster_id) VALUES (?, ?)",
                (qpk, cluster_id),
            )

        vec = ollama_embed(canonical)
        topic_vectors.append(vec)
        topic_meta.append({"cluster_id": cluster_id, "canonical_name": canonical,
                            "matched_text": canonical, "member_tags": member_tags})

    conn.commit()

    mat = np.vstack(topic_vectors).astype("float32")
    faiss.normalize_L2(mat)
    index = faiss.IndexFlatIP(mat.shape[1])
    index.add(mat)
    db_manager.save_faiss_index("topics", index, json.dumps(topic_meta))

    print(f"Generating aliases for {len(topic_meta)} clusters...")
    canonical_by_id = {t["cluster_id"]: t["canonical_name"] for t in topic_meta}
    alias_input = [{"cluster_id": t["cluster_id"], "canonical_name": t["canonical_name"]}
                    for t in topic_meta]

    ALIAS_CHUNK_SIZE = 15
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "integer"},
                "aliases": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["cluster_id", "aliases"]
        }
    }
    for start in range(0, len(alias_input), ALIAS_CHUNK_SIZE):
        chunk = alias_input[start:start + ALIAS_CHUNK_SIZE]
        try:
            alias_results = ollama_generate_json(
                ALIAS_SYSTEM_PROMPT, json.dumps(chunk, ensure_ascii=False), schema
            )
        except Exception as e:
            print(f"  ! alias generation failed for batch starting {start}: {e} -- skipping batch")
            continue

        positional_ok = len(alias_results) == len(chunk)

        for pos, item in enumerate(alias_results):
            if not isinstance(item, dict):
                continue
            raw_id = item.get("cluster_id", item.get("id"))
            aliases = item.get("aliases", item.get("topics", []))

            cid = None
            if raw_id in canonical_by_id:
                cid = raw_id
            elif positional_ok:
                cid = chunk[pos]["cluster_id"]
            else:
                continue

            for alias in aliases:
                alias = str(alias).strip()
                if not alias:
                    continue
                try:
                    vec = ollama_embed(alias)
                except Exception as e:
                    continue
                topic_vectors.append(vec)
                topic_meta.append({"cluster_id": cid, "canonical_name": canonical_by_id[cid],
                                    "matched_text": alias, "member_tags": []})

        mat = np.vstack(topic_vectors).astype("float32")
        faiss.normalize_L2(mat)
        index = faiss.IndexFlatIP(mat.shape[1])
        index.add(mat)
        db_manager.save_faiss_index("topics", index, json.dumps(topic_meta))

    conn.close()

def _lexical_match_clusters(query: str, topic_meta: list):
    q_norm = query.strip().lower()
    hits = {}
    for m in topic_meta:
        candidates = [m["canonical_name"]] + ([m["matched_text"]] if m["matched_text"] != m["canonical_name"] else [])
        for text in candidates:
            t_norm = text.strip().lower()
            if re.search(rf"\b{re.escape(q_norm)}\b", t_norm):
                cid = m["cluster_id"]
                if cid not in hits:
                    hits[cid] = (m["canonical_name"], text)
    return [(cid, name, matched) for cid, (name, matched) in hits.items()]

def _nearest_topic_clusters(query: str, index: faiss.Index, topic_meta: list, n: int = 8):
    q_vec = ollama_embed(query, task="query").reshape(1, -1).astype("float32")
    faiss.normalize_L2(q_vec)
    sims, idxs = index.search(q_vec, min(n, len(topic_meta)))

    best_per_cluster = {}
    for sim, idx in zip(sims[0], idxs[0]):
        if idx == -1:
            continue
        m = topic_meta[idx]
        distance = 1 - float(sim)
        cid = m["cluster_id"]
        if cid not in best_per_cluster or distance < best_per_cluster[cid][2]:
            best_per_cluster[cid] = (m["canonical_name"], m["matched_text"], distance)

    results = [(cid, name, matched, dist) for cid, (name, matched, dist) in best_per_cluster.items()]
    results.sort(key=lambda r: r[3])
    return results

def resolve_topics(db_manager, topic_strings: list[str]) -> dict[str, list[int]]:
    """topic string -> list of matched cluster_ids, lexical-first then embedding fallback."""
    index, meta_json = db_manager.load_faiss_index("topics")
    if index is None or meta_json is None:
        return {ts: [] for ts in topic_strings}
    
    topic_meta = json.loads(meta_json)
    results = {}
    for query in topic_strings:
        matched_cluster_ids = []
        lexical_hits = _lexical_match_clusters(query, topic_meta)
        for cid, name, matched in lexical_hits[:1]: # pick best lexical
            matched_cluster_ids.append(cid)
            
        if not matched_cluster_ids:
            candidates = _nearest_topic_clusters(query, index, topic_meta, n=8)
            for cid, name, matched, dist in candidates:
                if dist <= TOPIC_MATCH_THRESHOLD:
                    matched_cluster_ids.append(cid)
                    break # pick best embedding match under threshold
                    
        results[query] = matched_cluster_ids
    return results

def add_new_cluster(db_manager, canonical_name: str, source: str = 'lecture') -> int:
    conn = db_manager.conn
    cur = conn.execute(
        "INSERT INTO topic_clusters (canonical_name, member_count, source) VALUES (?, 0, ?)",
        (canonical_name, source)
    )
    cluster_id = cur.lastrowid
    conn.commit()

    index, meta_json = db_manager.load_faiss_index("topics")
    topic_meta = json.loads(meta_json) if meta_json else []
    
    vec = ollama_embed(canonical_name)
    topic_meta.append({
        "cluster_id": cluster_id,
        "canonical_name": canonical_name,
        "matched_text": canonical_name,
        "member_tags": []
    })

    if index is None:
        index = faiss.IndexFlatIP(len(vec))
    
    mat = np.array([vec], dtype="float32")
    faiss.normalize_L2(mat)
    index.add(mat)
    db_manager.save_faiss_index("topics", index, json.dumps(topic_meta))
    
    return cluster_id
