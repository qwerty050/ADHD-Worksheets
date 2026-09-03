import json
import logging
import os
import queue
import re
import shutil
import threading
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = logging.getLogger("pipeline")
logging.basicConfig(level=logging.INFO, format="%(message)s")

# In-memory session store: session_id -> dict of session data
SESSIONS = {}
ENV_PATH = Path(".env")

# One generation at a time: pipeline progress is streamed per-run, so
# concurrent runs would interleave their log lines.
_GENERATION_LOCK = threading.Lock()

_SAFE_NAME_RE = re.compile(r"[^\w.\- ]+")


def _safe_name(filename: Optional[str]) -> str:
    """Strip directories and odd characters from a client-supplied filename."""
    name = Path(filename or "upload").name
    cleaned = _SAFE_NAME_RE.sub("_", name).strip() or "upload"
    return cleaned


class ConfigUpdate(BaseModel):
    LLM_PROVIDER: str = ""
    OLLAMA_BASE: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    MODEL_EXTRACTION: str = ""
    MODEL_PEDAGOGY: str = ""
    MODEL_WRITER: str = ""
    MODEL_QUESTIONS: str = ""
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

    # Skip empty fields so clearing one field in the UI doesn't blank out
    # other settings in .env.
    for key, value in config.model_dump().items():
        if value:
            set_key(str(ENV_PATH), key, value)

    return {"status": "success", "note": "Restart the server for provider/model changes to take effect."}


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
def upload_kb(session_id: str, file: UploadFile = File(...)):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    kb_path = session["dir"] / _safe_name(file.filename)
    with open(kb_path, "wb") as f:
        f.write(file.file.read())

    session["kb"] = KnowledgeBase.load(str(kb_path))
    session["kb_path"] = kb_path
    session["kb_name"] = kb_path.stem
    return {"status": "success", "kb_name": session["kb_name"]}


@app.post("/api/sessions/{session_id}/kb/create")
def create_kb(session_id: str, name: str = Form(...)):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    kb_name = _safe_name(name)
    kb_path = session["dir"] / f"{kb_name}.cmkb"
    session["kb"] = KnowledgeBase.create(str(kb_path), name=kb_name)
    session["kb_path"] = kb_path
    session["kb_name"] = kb_name
    return {"status": "success"}


@app.get("/api/sessions/{session_id}/kb")
def kb_info(session_id: str):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")
    return session["kb"].kb_stats()


@app.post("/api/sessions/{session_id}/kb/ingest_questions")
def ingest_questions(session_id: str, files: list[UploadFile] = File(...)):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")

    ingested = 0
    for file in files:
        q_path = session["dir"] / _safe_name(file.filename)
        with open(q_path, "wb") as f:
            f.write(file.file.read())
        session["kb"].ingest_questions(q_path)
        ingested += 1

    return {"status": "success", "files_ingested": ingested}


@app.post("/api/sessions/{session_id}/kb/ingest_pdf")
def ingest_pdf(session_id: str, mode: str = Form("chunking"), files: list[UploadFile] = File(...)):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")

    ingested = 0
    for file in files:
        pdf_path = session["dir"] / _safe_name(file.filename)
        with open(pdf_path, "wb") as f:
            f.write(file.file.read())
        session["kb"].ingest_pdf(pdf_path, mode=mode)
        ingested += 1

    return {"status": "success", "files_ingested": ingested}


@app.post("/api/sessions/{session_id}/kb/cluster")
def cluster_kb(session_id: str):
    session = SESSIONS.get(session_id)
    if not session or not session["kb"]:
        raise HTTPException(status_code=404, detail="Session or KB not found")

    session["kb"].cluster()
    return {"status": "success"}


@app.post("/api/sessions/{session_id}/extract")
def extract_lecture(
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
    if json_file is not None and json_file.filename:
        with open(out_json_path, "wb") as f:
            f.write(json_file.file.read())
    elif json_text:
        try:
            parsed = json.loads(json_text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Pasted JSON is not valid JSON: {e}")
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
    elif pdf_file is not None and pdf_file.filename:
        pdf_path = session["dir"] / _safe_name(pdf_file.filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_file.file.read())
        # Run extraction
        run_extraction_pipeline(pdf_path, out_json_path)
    else:
        raise HTTPException(status_code=400, detail="No input provided")

    session["pedagogical_json_path"] = out_json_path
    return {"status": "success"}


class QueueLogHandler(logging.Handler):
    """Forwards pipeline log records into the SSE queue for one run."""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        try:
            self.q.put(self.format(record))
        except Exception:
            pass


@app.get("/api/sessions/{session_id}/generate")
def generate_lecture(
    session_id: str,
    objective: bool = False,
    newpage_per_question: bool = True,
    update_memory: bool = True,
    reuse: str = Query("prefer", pattern="^(prefer|never)$"),
):
    session = SESSIONS.get(session_id)
    if not session or not session["pedagogical_json_path"]:
        raise HTTPException(status_code=404, detail="Session or extraction not found")

    if not _GENERATION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another generation is already running")

    out_tex_path = session["dir"] / f"{session['lecture_id']}_output.tex"

    with open(session["pedagogical_json_path"], "r", encoding="utf-8") as f:
        pedagogical_json = json.load(f)

    cache = PipelineCache(
        session["pedagogical_json_path"],
        kb_id=str(session["kb_path"]) if session["kb_path"] else None,
        lecture_id=session["lecture_id"]
    )

    q: queue.Queue = queue.Queue()

    def run_gen():
        handler = QueueLogHandler(q)
        log.addHandler(handler)
        try:
            run_generation_pipeline(
                pedagogical_json=pedagogical_json,
                kb=session["kb"],
                lecture_id=session["lecture_id"],
                output_tex_path=out_tex_path,
                cache=cache,
                update_memory=update_memory,
                is_objective=objective,
                newpage_per_question=newpage_per_question,
                reuse=reuse,
            )
        except Exception as e:
            q.put(f"ERROR: {e}")
        finally:
            log.removeHandler(handler)
            _GENERATION_LOCK.release()
            q.put(None)  # EOF marker

    threading.Thread(target=run_gen, daemon=True).start()

    import asyncio

    async def event_generator():
        while True:
            try:
                msg = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.3)
                continue
            if msg is None:
                yield {"data": "None"}
                break
            if msg.strip():
                yield {"data": msg.strip()}

    return EventSourceResponse(event_generator())


@app.get("/api/sessions/{session_id}/download/{file_type}")
def download_file(session_id: str, file_type: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if file_type == "tex":
        if not session.get("lecture_id"):
            raise HTTPException(status_code=404, detail="No generated worksheet in this session")
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
