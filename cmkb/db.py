import sqlite3
import faiss
import numpy as np
import tempfile
import os
import shutil

class DBManager:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        # Metadata and FAISS storage
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS faiss_indexes (
                name TEXT PRIMARY KEY,
                index_blob BLOB,
                meta_json TEXT
            )
        """)
        
        # Original Questions Layer
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                pk INTEGER PRIMARY KEY AUTOINCREMENT,
                exam TEXT,
                qid TEXT,
                question TEXT,
                answer TEXT,
                options_json TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS question_tags (
                question_pk INTEGER,
                raw_tag TEXT,
                FOREIGN KEY(question_pk) REFERENCES questions(pk)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_clusters (
                cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT,
                member_count INTEGER,
                source TEXT DEFAULT 'pyq' -- 'pyq' or 'lecture'
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS question_topics (
                question_pk INTEGER,
                cluster_id INTEGER,
                FOREIGN KEY(question_pk) REFERENCES questions(pk),
                FOREIGN KEY(cluster_id) REFERENCES topic_clusters(cluster_id)
            )
        """)

        # New Tables for Lectures and Sections
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lecture_topics (
                lecture_id TEXT,
                cluster_id INTEGER,
                status TEXT, -- 'confirmed' or 'new'
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (lecture_id, cluster_id),
                FOREIGN KEY(cluster_id) REFERENCES topic_clusters(cluster_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                section_id TEXT PRIMARY KEY,
                lecture_id TEXT,
                latex TEXT,
                summary TEXT,
                source_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS section_topics (
                section_id TEXT,
                cluster_id INTEGER,
                PRIMARY KEY (section_id, cluster_id),
                FOREIGN KEY(section_id) REFERENCES sections(section_id),
                FOREIGN KEY(cluster_id) REFERENCES topic_clusters(cluster_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pdf_tree (
                doc_id TEXT PRIMARY KEY,
                doc_title TEXT,
                tree_json TEXT
            )
        """)
        self.conn.commit()

    def set_meta(self, key: str, value: str):
        self.conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_meta(self, key: str) -> str:
        row = self.conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def save_faiss_index(self, name: str, index: faiss.Index, meta_json: str):
        # faiss.serialize_index works on most faiss versions. If not, use tempfile write_index/read_index fallback.
        try:
            chunk = faiss.serialize_index(index)
            blob = chunk.tobytes() if hasattr(chunk, 'tobytes') else bytes(chunk)
        except AttributeError:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                temp_path = tf.name
            faiss.write_index(index, temp_path)
            with open(temp_path, "rb") as f:
                blob = f.read()
            os.remove(temp_path)
            
        self.conn.execute(
            "INSERT OR REPLACE INTO faiss_indexes (name, index_blob, meta_json) VALUES (?, ?, ?)",
            (name, blob, meta_json)
        )
        self.conn.commit()

    def load_faiss_index(self, name: str) -> tuple[faiss.Index, str]:
        row = self.conn.execute("SELECT index_blob, meta_json FROM faiss_indexes WHERE name = ?", (name,)).fetchone()
        if not row:
            return None, None
        
        blob, meta_json = row["index_blob"], row["meta_json"]
        try:
            index = faiss.deserialize_index(np.frombuffer(blob, dtype=np.uint8))
        except AttributeError:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(blob)
                temp_path = tf.name
            index = faiss.read_index(temp_path)
            os.remove(temp_path)

        return index, meta_json

    def atomic_save(self, dest_path: str):
        """Not strictly needed since we update the single file in place, 
        but if we do in-memory or want to copy/backup we can use sqlite3 backup api"""
        if self.path != dest_path:
            with sqlite3.connect(dest_path) as dst_conn:
                self.conn.backup(dst_conn)
                
    def close(self):
        self.conn.close()
