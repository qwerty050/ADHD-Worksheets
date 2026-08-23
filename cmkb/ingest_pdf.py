import json
import faiss
import numpy as np
import uuid
import os
from .llm import ollama_embed, ollama_generate_json

def ingest_pdf_chunking(db_manager, pdf_path: str):
    """
    Fallback implementation: if pymupdf/PyMuPDF is available, we extract text.
    For this stub, we just chunk the document text.
    """
    doc_id = str(uuid.uuid4())
    doc_title = os.path.basename(pdf_path)
    
    # Try to extract text, fallback to a mock if no library
    text = ""
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        for page in doc:
            text += page.get_text()
    except ImportError:
        text = f"Mock text for {doc_title} (Install PyMuPDF for real extraction)"
        print("PyMuPDF (pymupdf) not installed, using mock text.")

    # Simple fixed-size window chunking
    chunk_size = 1000
    overlap = 200
    chunks = []
    
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({
            "text": text[start:end],
            "heading_path": "General", # Mock breadcrumb
            "page_range": [1, 1] # Mock page range
        })
        start += (chunk_size - overlap)

    index, meta_json = db_manager.load_faiss_index("documents")
    docs_meta = json.loads(meta_json) if meta_json else []
    
    vectors = []
    for chunk in chunks:
        # Prepend heading breadcrumb
        embed_text = f"{doc_title} > {chunk['heading_path']} : {chunk['text']}"
        vec = ollama_embed(embed_text, task="document")
        vectors.append(vec)
        docs_meta.append({
            "doc_id": doc_id,
            "doc_title": doc_title,
            "heading_path": chunk["heading_path"],
            "text": chunk["text"],
            "page_range": chunk["page_range"]
        })

    if vectors:
        mat = np.vstack(vectors).astype("float32")
        faiss.normalize_L2(mat)
        if index is None:
            index = faiss.IndexFlatIP(mat.shape[1])
        index.add(mat)
        db_manager.save_faiss_index("documents", index, json.dumps(docs_meta))
        
    print(f"Ingested PDF {doc_title} via chunking with {len(vectors)} chunks.")

def ingest_pdf_page_index(db_manager, pdf_path: str):
    """
    PageIndex implementation (Reasoning-based retrieval).
    Builds a tree in the db_manager.
    """
    doc_id = str(uuid.uuid4())
    doc_title = os.path.basename(pdf_path)
    
    from .pageindex import pageindex_main, config
    from .config import PAGEINDEX_MODEL
    
    opt = config(
        model=PAGEINDEX_MODEL,
        toc_check_page_num=20,
        max_page_num_each_node=10,
        max_token_num_each_node=20000,
        if_add_node_id='yes',
        if_add_node_summary='yes',
        if_add_doc_description='no',
        if_add_node_text='yes'
    )
    
    print(f"Building PageIndex tree for {doc_title}...")
    toc_with_page_number = pageindex_main(pdf_path, opt)
    
    conn = db_manager.conn
    conn.execute(
        "INSERT INTO pdf_tree (doc_id, doc_title, tree_json) VALUES (?, ?, ?)",
        (doc_id, doc_title, json.dumps(toc_with_page_number))
    )
    conn.commit()
    print(f"Saved PageIndex tree for {doc_title}.")

def ingest_pdf(db_manager, pdf_path: str, mode: str = "chunking"):
    if mode == "chunking":
        ingest_pdf_chunking(db_manager, pdf_path)
    elif mode == "page_index":
        ingest_pdf_page_index(db_manager, pdf_path)
    else:
        raise ValueError(f"Unknown PDF ingest mode: {mode}")
