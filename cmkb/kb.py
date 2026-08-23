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
from .llm import ollama_embed
from .config import EMBED_MODEL

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

    def query(self, topics: List[str], lecture_id: Optional[str] = None, k: int = 8) -> Dict[str, Any]:
        self._check_embed_model()
        resolved = resolve_topics(self.db, topics)
        
        response = {
            "questions": [],
            "book_context": [],
            "already_covered": []
        }
        
        # 1. Questions Retrieval (Exact Match)
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
                    SELECT q.exam, q.qid, q.question, q.answer
                    FROM questions q
                    JOIN question_topics qt ON qt.question_pk = q.pk
                    WHERE qt.cluster_id = ?
                """, (cid,)).fetchall()
                
                matches = [{"source": r["exam"], "qid": r["qid"], "question": r["question"], "answer": r["answer"]} for r in rows]
                
                response["questions"].append({
                    "cluster_id": cid,
                    "canonical_topic": canonical,
                    "matches": matches
                })
                
        # 2a. Book Context Retrieval (Hybrid FAISS placeholder)
        doc_index, doc_meta_json = self.db.load_faiss_index("documents")
        if doc_index and doc_meta_json:
            doc_meta = json.loads(doc_meta_json)
            for topic_str in topics:
                q_vec = ollama_embed(topic_str, task="query").reshape(1, -1).astype("float32")
                faiss.normalize_L2(q_vec)
                sims, idxs = doc_index.search(q_vec, k)
                
                for sim, idx in zip(sims[0], idxs[0]):
                    if idx != -1:
                        m = doc_meta[idx]
                        response["book_context"].append({
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
            for topic_str in topics:
                print(f"Traversing PageIndex tree of {doc_title} for topic '{topic_str}'...")
                # Note: tree is a list of nodes (chapters) typically, let's treat it as a root with children
                root = {"title": doc_title, "children": tree} if isinstance(tree, list) else tree
                results = traverse_page_index(topic_str, root)
                for res in results:
                    response["book_context"].append({
                        "doc_title": doc_title,
                        "heading_path": res["heading_path"],
                        "text": res["text"],
                        "page_range": res["page_range"]
                    })
        # Note: Deduplication would happen here
        
        # 3. Already Covered Retrieval
        summ_index, summ_meta_json = self.db.load_faiss_index("summaries")
        if summ_index and summ_meta_json:
            summ_meta = json.loads(summ_meta_json)
            for topic_str in topics:
                q_vec = ollama_embed(topic_str, task="query").reshape(1, -1).astype("float32")
                faiss.normalize_L2(q_vec)
                sims, idxs = summ_index.search(q_vec, 3) # top 3
                
                for sim, idx in zip(sims[0], idxs[0]):
                    if idx != -1:
                        # simple threshold check
                        if sim > 0.4:
                            m = summ_meta[idx]
                            response["already_covered"].append({
                                "topic": topic_str,
                                "lecture_id": m["lecture_id"],
                                "section_id": m["section_id"],
                                "summary_snippet": m["summary"]
                            })

        return response
