import json
import faiss
import numpy as np
from .llm import ollama_embed, ollama_generate_json

BATCH_SYSTEM_PROMPT = """You are tagging exam questions from a course with topic labels, \
to build a retrieval index. You will be given a JSON array of questions. For each \
question, output a short topic label identifying the specific concept being tested.

Rules:
1. Tag the underlying concept being tested, not the surface scenario or wording.
2. Be as specific as the question warrants (e.g. "backpropagation chain rule" \
rather than "neural networks", if that's what's actually being tested).
3. Use both the question and the answer to determine the topic.
4. If a question tests more than one concept, output up to 2 labels, most \
central concept first.
5. Use plain, conventional textbook terminology.
6. Output ONLY valid JSON, no commentary, matching this schema exactly:
[{"id": <question id>, "topics": ["<label 1>", "<label 2 if applicable>"]}]
"""

def question_text_for_embedding(q: dict) -> str:
    parts = [q["question"]]
    if q.get("answer"):
        parts.append(str(q["answer"]))
    return " ".join(parts)

def ingest_questions(db_manager, json_path: str):
    with open(json_path, "r") as f:
        exams = json.load(f)

    conn = db_manager.conn

    # Load existing FAISS index or create
    index, meta_json = db_manager.load_faiss_index("questions")
    question_vectors = []
    question_meta = json.loads(meta_json) if meta_json else []

    for exam in exams:
        exam_title = exam.get("exam") or exam.get("title") or "unknown_exam"
        questions = exam["questions"]

        pks_by_local_id = {}
        skipped = 0
        new_questions = []
        for q in questions:
            existing = conn.execute(
                "SELECT pk FROM questions WHERE exam = ? AND qid = ?",
                (exam_title, str(q["id"])),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            cur = conn.execute(
                "INSERT INTO questions (exam, qid, question, answer, options_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    exam_title,
                    str(q["id"]),
                    q["question"],
                    str(q.get("answer", "")),
                    json.dumps(q.get("options")),
                ),
            )
            pk = cur.lastrowid
            pks_by_local_id[q["id"]] = pk
            new_questions.append(q)

            vec = ollama_embed(question_text_for_embedding(q))
            question_vectors.append(vec)
            question_meta.append({
                "pk": pk, "exam": exam_title, "qid": q["id"],
                "question": q["question"], "answer": q.get("answer", ""),
            })

        if skipped:
            print(f"  Skipped {skipped} questions already ingested from '{exam_title}'.")
        if not new_questions:
            continue

        conn.commit()

        tag_input = [
            {"id": q["id"], "question": q["question"], "answer": q.get("answer", "")}
            for q in new_questions
        ]
        print(f"Tagging {len(tag_input)} questions from '{exam_title}'...")
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "topics": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2}
                },
                "required": ["id", "topics"]
            }
        }
        try:
            tagged = ollama_generate_json(
                BATCH_SYSTEM_PROMPT, json.dumps(tag_input, ensure_ascii=False), schema
            )
        except Exception as e:
            print(f"  ! tagging failed for {exam_title}: {e}")
            continue

        if not isinstance(tagged, list):
            continue

        for item in tagged:
            if not isinstance(item, dict):
                continue
            pk = pks_by_local_id.get(item.get("id"))
            if pk is None:
                continue
            for raw_tag in item.get("topics", []):
                conn.execute(
                    "INSERT INTO question_tags (question_pk, raw_tag) VALUES (?, ?)",
                    (pk, str(raw_tag).strip().lower()),
                )
        conn.commit()

    if question_vectors:
        mat = np.vstack(question_vectors).astype("float32")
        faiss.normalize_L2(mat)
        if index is None:
            index = faiss.IndexFlatIP(mat.shape[1])
        index.add(mat)
        db_manager.save_faiss_index("questions", index, json.dumps(question_meta))

    print(f"Ingested {len(question_vectors)} new questions.")
