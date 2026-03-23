import json
import requests
import numpy as np
import faiss
import os
import pickle

# =========================
# CONFIG1
# =========================
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "nomic-embed-text:latest"

INDEX_FILE = "faiss_index.bin"
DOCS_FILE = "docs.pkl"

JSON_FILE = "../src/supporting/quiz.json"   # your file


# =========================
# LOAD DATA
# =========================
def load_data(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)

    docs = []
    for quiz in data:
        for q in quiz["questions"]:
            text = q["question"]

            # Combine Q + Answer for better embedding
            if "answer" in q:
                text += " " + q["answer"]

            docs.append({
                "text": text,
                "question": q["question"],
                "answer": q.get("answer", ""),
                "meta": {
                    "quiz": quiz["title"],
                    "id": q["id"]
                }
            })
    return docs


# =========================
# EMBEDDING FUNCTION
# =========================
def get_embedding(text):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": text
        }
    )

    if response.status_code != 200:
        raise Exception(f"Ollama error: {response.text}")

    return response.json()["embedding"]


# =========================
# BUILD INDEX
# =========================
def build_index(docs):
    print("Generating embeddings... (this will test your patience)")

    embeddings = []
    for i, doc in enumerate(docs):
        emb = get_embedding(doc["text"])
        embeddings.append(emb)

        if i % 10 == 0:
            print(f"Processed {i}/{len(docs)}")

    embeddings = np.array(embeddings).astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    return index, embeddings


# =========================
# SAVE / LOAD
# =========================
def save_index(index, docs):
    faiss.write_index(index, INDEX_FILE)
    with open(DOCS_FILE, "wb") as f:
        pickle.dump(docs, f)


def load_index():
    if not os.path.exists(INDEX_FILE):
        return None, None

    index = faiss.read_index(INDEX_FILE)
    with open(DOCS_FILE, "rb") as f:
        docs = pickle.load(f)

    return index, docs


# =========================
# SEARCH
# =========================
# def search(index, docs, query, k=5):
#     q_emb = np.array([get_embedding(query)]).astype("float32")

#     distances, indices = index.search(q_emb, k)

#     results = []
#     for i in indices[0]:
#         results.append(docs[i])

#     return results
# def search(index, docs, query, k=5):
#     q_emb = np.array([get_embedding(query)]).astype("float32")
#     distances, indices = index.search(q_emb, k * 3)  # get more candidates

#     query_lower = query.lower()

#     scored = []
#     for rank, i in enumerate(indices[0]):
#         doc = docs[i]

#         text = doc["text"].lower()

#         # keyword bonus
#         keyword_score = 1 if query_lower in text else 0

#         # combine scores (lower distance = better)
#         score = -distances[0][rank] + (2 * keyword_score)

#         scored.append((score, doc))

#     scored.sort(reverse=True, key=lambda x: x[0])

#     return [d for _, d in scored[:k]]

def search(index, docs, query, threshold=0.7):
    q_emb = np.array([get_embedding(query)]).astype("float32")
    D, I = index.search(q_emb, len(docs))  # search ALL

    results = []
    for dist, idx in zip(D[0], I[0]):
        if dist < threshold:
            results.append(docs[idx])

    return results


# =========================
# MAIN
# =========================
def main():
    index, docs = load_index()

    if index is None:
        print("No index found. Building new one...")
        docs = load_data(JSON_FILE)
        index, _ = build_index(docs)
        save_index(index, docs)
        print("Index built and saved.")
    else:
        print("Loaded existing index.")

    print("\nType your query (or 'exit'):\n")

    while True:
        query = input(">> ")

        if query.lower() == "exit":
            break

        results = search(index, docs, query, threshold=0.7)

        print("\nTop Results:\n")
        for i, r in enumerate(results):
            print(f"{i+1}. [{r['meta']['quiz']} | Q{r['meta']['id']}]")
            print("Q:", r["question"])
            print("A:", r["answer"])
            print("-" * 50)


if __name__ == "__main__":
    main()