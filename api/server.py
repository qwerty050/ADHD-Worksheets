import os
import json
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from dotenv import dotenv_values, set_key

from cmkb.kb import KnowledgeBase
from extraction.pipeline import run_extraction_pipeline
from generation.pipeline import run_generation_pipeline
from shared.cache import PipelineCache

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: session_id -> dict of session data
SESSIONS = {}
ENV_PATH = Path(".env")

class ConfigUpdate(BaseModel):
    OLLAMA_BASE: str = ""
    MODEL_EXTRACTION: str = ""
    MODEL_QUESTION_EXTRACT: str = ""
    MODEL_PEDAGOGY: str = ""
    MODEL_THEORY: str = ""
    MODEL_QUESTIONS: str = ""
    MODEL_QUESTION_FILTER: str = ""
    MODEL_REVIEW: str = ""
    MODEL_CONTEXT_SUMMARY: str = ""
    EMBED_MODEL: str = ""
    TAG_MODEL: str = ""
    PAGEINDEX_MODEL: str = ""

@app.get("/api/config")
def get_config():
    if not ENV_PATH.exists():
        if Path(".env.example").exists():
            shutil.copy(".env.example", ".env")
        else:
            return {}
    return dotenv_values(ENV_PATH)

@app.post("/api/config")
def update_config(config: ConfigUpdate):
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    
    config_dict = config.dict()
    for key, value in config_dict.items():
        set_key(str(ENV_PATH), key, value)
    
    return {"status": "success"}

@app.post("/api/sessions")
def create_session():
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"adhd_session_{session_id}_")
    SESSIONS[session_id] = {
        "dir": Path(temp_dir),
        "kb": None,
        "kb_path": None,
        "kb_name": None,
        "lecture_id": None,
        "pedagogical_json_path": None
    }
    return {"session_id": session_id}

@app.post("/api/sessions/{session_id}/kb/upload")
async def upload_kb(session_id: str, file: UploadFile = File(...)):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    kb_path = session["dir"] / file.filename
    with open(kb_path, "wb") as f:
        f.write(await file.read())
        
    session["kb"] = KnowledgeBase.load(str(kb_path))
    session["kb_path"] = kb_path
    session["kb_name"] = kb_path.stem
    return {"status": "success", "kb_name": session["kb_name"]}

@app.post("/api/sessions/{session_id}/kb/create")
def create_kb(session_id: str, name: str = Form(...)):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    kb_path = session["dir"] / f"{name}.cmkb"
    session["kb"] = KnowledgeBase.create(str(kb_path), name=name)
    session["kb_path"] = kb_path
    session["kb_name"] = name
    return {"status": "success"}

@app.post("/api/sessions/{session_id}/kb/ingest_questions")
async def ingest_questions(session_id: str, files: list[UploadFile] = File(...)):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")
    
    for file in files:
        q_path = session["dir"] / file.filename
        with open(q_path, "wb") as f:
            f.write(await file.read())
        session["kb"].ingest_questions(q_path)
        
    return {"status": "success"}

@app.post("/api/sessions/{session_id}/kb/ingest_pdf")
async def ingest_pdf(session_id: str, mode: str = Form("chunking"), files: list[UploadFile] = File(...)):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")
    
    for file in files:
        pdf_path = session["dir"] / file.filename
        with open(pdf_path, "wb") as f:
            f.write(await file.read())
        session["kb"].ingest_pdf(pdf_path, mode=mode)
        
    return {"status": "success"}

@app.post("/api/sessions/{session_id}/kb/cluster")
def cluster_kb(session_id: str):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")
    
    session["kb"].cluster()
    return {"status": "success"}

@app.post("/api/sessions/{session_id}/extract")
async def extract_lecture(
    session_id: str, 
    lecture_id: str = Form(...),
    pdf_file: Optional[UploadFile] = File(None),
    json_file: Optional[UploadFile] = File(None),
    json_text: Optional[str] = Form(None)
):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session["lecture_id"] = lecture_id
    out_json_path = session["dir"] / f"{lecture_id}_pedagogical.json"
    
    # Priority: json_file > json_text > pdf_file
    if json_file:
        with open(out_json_path, "wb") as f:
            f.write(await json_file.read())
    elif json_text:
        with open(out_json_path, "w", encoding="utf-8") as f:
            f.write(json_text)
    elif pdf_file:
        pdf_path = session["dir"] / pdf_file.filename
        with open(pdf_path, "wb") as f:
            f.write(await pdf_file.read())
        # Run extraction
        run_extraction_pipeline(pdf_path, out_json_path)
    else:
        raise HTTPException(status_code=400, detail="No input provided")

    session["pedagogical_json_path"] = out_json_path
    return {"status": "success"}

@app.get("/api/sessions/{session_id}/generate")
async def generate_lecture(
    session_id: str,
    objective: bool = False,
    review: bool = True,
    newpage_per_question: bool = True,
    update_memory: bool = True
):
    session = SESSIONS.get(session_id)
    if not session or not session["pedagogical_json_path"]:
        raise HTTPException(status_code=404, detail="Session or extraction not found")
        
    out_tex_path = session["dir"] / f"{session['lecture_id']}_output.tex"
    
    with open(session["pedagogical_json_path"], "r", encoding="utf-8") as f:
        pedagogical_json = json.load(f)
        
    cache = PipelineCache(
        session["pedagogical_json_path"], 
        kb_id=str(session["kb_path"]) if session["kb_path"] else None, 
        lecture_id=session["lecture_id"]
    )
    
    # Normally this is sync and slow. For a real app we might run it in a thread.
    # To keep it simple and fulfill the requirement of streaming progress, 
    # we would need to capture stdout or run it asynchronously.
    # Given the constraint to not rewrite pipeline logic, we will just run it.
    import sys
    from io import StringIO
    import threading
    import queue
    import time
    
    q = queue.Queue()
    
    class StdoutRedirector:
        def __init__(self, queue):
            self.queue = queue
        def write(self, msg):
            self.queue.put(msg)
            sys.__stdout__.write(msg)
        def flush(self):
            sys.__stdout__.flush()
            
    def run_gen():
        old_stdout = sys.stdout
        sys.stdout = StdoutRedirector(q)
        try:
            run_generation_pipeline(
                pedagogical_json=pedagogical_json,
                kb=session["kb"],
                lecture_id=session["lecture_id"],
                output_tex_path=out_tex_path,
                cache=cache,
                update_memory=update_memory,
                is_objective=objective,
                review=review,
                newpage_per_question=newpage_per_question
            )
            q.put(None) # EOF marker
        except Exception as e:
            q.put(f"ERROR: {str(e)}")
            q.put(None)
        finally:
            sys.stdout = old_stdout

    threading.Thread(target=run_gen).start()
    
    async def event_generator():
        while True:
            try:
                # get_nowait doesn't block async loop, but time.sleep(0.1) below handles it
                # Using asyncio.sleep to not block the event loop
                msg = q.get_nowait()
                if msg is None:
                    yield {"data": "None"}
                    break
                if msg.strip():
                    yield {"data": msg.strip()}
            except queue.Empty:
                import asyncio
                await asyncio.sleep(0.5)
                continue
                
    return EventSourceResponse(event_generator())

@app.get("/api/sessions/{session_id}/download/{file_type}")
def download_file(session_id: str, file_type: str, background_tasks: BackgroundTasks):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if file_type == "tex":
        path = session["dir"] / f"{session['lecture_id']}_output.tex"
        filename = f"{session['lecture_id']}_output.tex"
    elif file_type == "cmkb":
        path = session["kb_path"]
        filename = path.name if path else "kb.cmkb"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
        
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(path, filename=filename)

@app.delete("/api/sessions/{session_id}")
def cleanup_session(session_id: str):
    session = SESSIONS.pop(session_id, None)
    if session and session["dir"].exists():
        shutil.rmtree(session["dir"])
    return {"status": "success"}
