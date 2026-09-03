import json
import faiss
import numpy as np
from typing import List, Dict, Any, Optional

from .db import DBManager
from .ingest_questions import ingest_questions as _ingest_questions
from .ingest_pdf import ingest_pdf as _ingest_pdf
from .ingest_lecture import ingest_lecture as _ingest_lecture
from .ingest_section import ingest_section as _ingest_section
from .topics import build_topic_clusters as _build_topic_clusters, resolve_topics
from .llm import ollama_embed_batch
from .config import EMBED_MODEL

REUSE_MODES = ("prefer", "never")


class KnowledgeBase:
    def __init__(self, path: str):
        self.path = path
        self.db = DBManager(path)

    @classmethod
    def create(cls, path: str, name: str, pdf_mode: str = "chunking", embed_model: str = EMBED_MODEL, embed_dim: int = 768):
        db = DBManager(path)
        db.set_meta("course_name", name)
        db.set_meta("pdf_mode", pdf_mode)
        db.set_meta("embed_model", embed_model)
        db.set_meta("embed_dim", str(embed_dim))
        return cls(path)

    @classmethod
    def load(cls, path: str):
        return cls(path)

    def _check_embed_model(self, force_reembed: bool = False):
        stored_model = self.db.get_meta("embed_model")
        if stored_model and stored_model != EMBED_MODEL and not force_reembed:
            raise ValueError(f"Embedding model mismatch! Stored: {stored_model}, Current: {EMBED_MODEL}. Use force_reembed=True to ignore.")

    def ingest_questions(self, questions_json_path: str):
        self._check_embed_model()
        _ingest_questions(self.db, questions_json_path)

    def cluster(self):
        self._check_embed_model()
        _build_topic_clusters(self.db)

    def ingest_pdf(self, pdf_path: str, mode: Optional[str] = None):
        self._check_embed_model()
        mode = mode or self.db.get_meta("pdf_mode") or "chunking"
        _ingest_pdf(self.db, pdf_path, mode)

    def ingest_lecture(self, lecture_json_path: str, lecture_id: str):
        self._check_embed_model()
        _ingest_lecture(self.db, lecture_json_path, lecture_id)

    def ingest_section(self, section_json: dict, summary: str, latex: str, lecture_id: str, topics: List[str]) -> str:
        self._check_embed_model()
        return _ingest_section(self.db, lecture_id, section_json, summary, latex, topics)

    def update(self, lecture_id: str, section_json: dict, summary: str, latex: str, topics: List[str]) -> str:
        """Alias for ingest_section as specified in requirements."""
        return self.ingest_section(section_json, summary, latex, lecture_id, topics)

    def query(self, topics: List[str], lecture_id: Optional[str] = None, k: int = 8, reuse: str = "prefer") -> Dict[str, Any]:
        """
        Retrieve PYQs, book context and previously-covered summaries for a section.

        reuse: 'prefer' serves never-used questions first and only falls back to
        already-used ones (flagged repeat=True) when a topic's pool is exhausted;
        'never' hard-excludes used questions.
        """
        if reuse not in REUSE_MODES:
            raise ValueError(f"reuse must be one of {REUSE_MODES}, got {reuse!r}")
        self._check_embed_model()
        resolved = resolve_topics(self.db, topics)

        response = {
            "questions": [],
            "book_context": [],
            "already_covered": []
        }

        # 1. Questions Retrieval (tag match) with usage tracking
        conn = self.db.conn
        for topic_str, cluster_ids in resolved.items():
            if not cluster_ids:
                response["questions"].append({
                    "topic": topic_str,
                    "status": "no_cluster_match"
                })
                continue

            for cid in cluster_ids:
                cluster_info = conn.execute("SELECT canonical_name FROM topic_clusters WHERE cluster_id = ?", (cid,)).fetchone()
                canonical = cluster_info["canonical_name"] if cluster_info else "Unknown"

                rows = conn.execute("""
                    SELECT q.pk, q.exam, q.qid, q.question, q.answer, q.options_json,
                           EXISTS(SELECT 1 FROM question_usage u WHERE u.question_pk = q.pk) AS used
                    FROM questions q
                    JOIN question_topics qt ON qt.question_pk = q.pk
                    WHERE qt.cluster_id = ?
                """, (cid,)).fetchall()

                def to_match(r, repeat):
                    try:
                        options = json.loads(r["options_json"]) if r["options_json"] else None
                    except (json.JSONDecodeError, TypeError):
                        options = None
                    return {
                        "pk": r["pk"],
                        "source": r["exam"],
                        "qid": r["qid"],
                        "question": r["question"],
                        "answer": r["answer"],
                        "options": options,
                        "used": bool(r["used"]),
                        "repeat": repeat,
                    }

                unused = [to_match(r, repeat=False) for r in rows if not r["used"]]
                already_used = [to_match(r, repeat=True) for r in rows if r["used"]]

                if reuse == "never":
                    matches = unused
                else:  # prefer
                    matches = unused if unused else already_used

                if matches:
                    response["questions"].append({
                        "cluster_id": cid,
                        "canonical_topic": canonical,
                        "matches": matches
                    })

        # 2. Book Context Retrieval
        doc_index, doc_meta_json = self.db.load_faiss_index("documents")
        if doc_index and doc_meta_json:
            doc_meta = json.loads(doc_meta_json)
            query_vecs = ollama_embed_batch(topics, task="query")
            for topic_str, q_vec in zip(topics, query_vecs):
                vec = q_vec.reshape(1, -1).astype("float32")
                faiss.normalize_L2(vec)
                sims, idxs = doc_index.search(vec, k)

                for sim, idx in zip(sims[0], idxs[0]):
                    if idx != -1:
                        m = doc_meta[idx]
                        response["book_context"].append({
                            "topic": topic_str,
                            "doc_title": m["doc_title"],
                            "heading_path": m["heading_path"],
                            "text": m["text"],
                            "page_range": m["page_range"]
                        })

        # 2b. Book Context Retrieval (PageIndex traversal)
        from .llm import traverse_page_index
        trees = conn.execute("SELECT doc_title, tree_json FROM pdf_tree").fetchall()
        for row in trees:
            doc_title = row["doc_title"]
            tree = json.loads(row["tree_json"])
            # page_index_main stores {"doc_name": ..., "structure": [...]}; normalize to a node list
            if isinstance(tree, dict):
                tree = tree.get("structure", [])
            if not isinstance(tree, list):
                continue
            root = {"title": doc_title, "children": tree}
            for topic_str in topics:
                print(f"Traversing PageIndex tree of {doc_title} for topic '{topic_str}'...")
                results = traverse_page_index(topic_str, root)
                for res in results:
                    response["book_context"].append({
                        "topic": topic_str,
                        "doc_title": doc_title,
                        "heading_path": res["heading_path"],
                        "text": res["text"],
                        "page_range": res["page_range"]
                    })

        # Dedupe book context entries (chunking + pageindex may overlap)
        seen_ctx = set()
        deduped_context = []
        for entry in response["book_context"]:
            key = (entry.get("doc_title"), entry.get("heading_path"), tuple(entry.get("page_range") or []))
            if key in seen_ctx:
                continue
            seen_ctx.add(key)
            deduped_context.append(entry)
        response["book_context"] = deduped_context

        # 3. Already Covered Retrieval (summaries from PAST lectures only)
        summ_index, summ_meta_json = self.db.load_faiss_index("summaries")
        if summ_index and summ_meta_json:
            summ_meta = json.loads(summ_meta_json)
            query_vecs = ollama_embed_batch(topics, task="query")
            for topic_str, q_vec in zip(topics, query_vecs):
                vec = q_vec.reshape(1, -1).astype("float32")
                faiss.normalize_L2(vec)
                sims, idxs = summ_index.search(vec, 3)  # top 3

                for sim, idx in zip(sims[0], idxs[0]):
                    if idx == -1:
                        continue
                    if sim <= 0.4:
                        continue
                    m = summ_meta[idx]
                    # Never self-match: sections of the lecture currently being generated
                    # are committed mid-run and must not count as "already covered".
                    if lecture_id and m.get("lecture_id") == lecture_id:
                        continue
                    response["already_covered"].append({
                        "topic": topic_str,
                        "lecture_id": m["lecture_id"],
                        "section_id": m["section_id"],
                        "summary_snippet": m["summary"]
                    })

        return response

    def mark_questions_used(self, used_items: List[Dict[str, Any]], lecture_id: str):
        """
        Persist that these questions were consumed by a worksheet section.

        used_items: [{"pk": int, "exam": str, "qid": str, "action": "included"|"adapted"}]
        Idempotent per (question_pk, lecture_id).
        """
        conn = self.db.conn
        for item in used_items:
            pk = item.get("pk")
            if pk is None:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO question_usage (question_pk, exam, qid, lecture_id, action)
                   VALUES (?, ?, ?, ?, ?)""",
                (pk, item.get("exam"), item.get("qid"), lecture_id, item.get("action", "included")),
            )
        conn.commit()

    def usage_stats(self) -> Dict[str, int]:
        conn = self.db.conn
        total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        used = conn.execute("SELECT COUNT(DISTINCT question_pk) FROM question_usage").fetchone()[0]
        return {"total_questions": total, "used_questions": used}

    def kb_stats(self) -> Dict[str, Any]:
        """Overview counts for inspection / the web UI."""
        conn = self.db.conn
        exams = conn.execute("SELECT COUNT(DISTINCT exam) FROM questions").fetchone()[0]
        clusters = conn.execute("SELECT COUNT(*) FROM topic_clusters").fetchone()[0]
        sections = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        lectures = conn.execute("SELECT COUNT(DISTINCT lecture_id) FROM lecture_topics").fetchone()[0]
        _, doc_meta_json = self.db.load_faiss_index("documents")
        documents = len(json.loads(doc_meta_json)) if doc_meta_json else 0
        stats = {
            "name": self.db.get_meta("course_name"),
            "embed_model": self.db.get_meta("embed_model"),
            "questions": conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            "exams": exams,
            "topic_clusters": clusters,
            "sections": sections,
            "lectures": lectures,
            "document_chunks": documents,
        }
        stats.update(self.usage_stats())
        return stats
