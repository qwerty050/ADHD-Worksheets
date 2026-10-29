"""Hermetic test helpers: a fake LLM client and a fake KB. No network, no Ollama."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeLLMClient:
    """Serves queued replies per call type (writer / questions) and records prompts."""

    def __init__(self, writer_replies=None, question_replies=None):
        self.replies = {"writer": list(writer_replies or []), "questions": list(question_replies or [])}
        self.calls = []

    def generate(self, prompt, model_name, system=None, as_json=False, max_tokens=None):
        from generation.prompts import SYSTEM_PROMPT_SECTION_WRITER, SYSTEM_PROMPT_QUESTION_BUILDER

        if system == SYSTEM_PROMPT_SECTION_WRITER:
            kind = "writer"
        elif system == SYSTEM_PROMPT_QUESTION_BUILDER:
            kind = "questions"
        else:
            raise AssertionError("unexpected LLM call")
        self.calls.append((kind, prompt))
        if not self.replies[kind]:
            raise AssertionError(f"no queued {kind} reply")
        reply = self.replies[kind].pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


class FakeKB:
    def __init__(self, questions=None):
        self.questions = questions or []
        self.updates = []
        self.marked = []

    def query(self, topics, lecture_id=None, reuse="prefer"):
        return {"questions": self.questions, "book_context": [], "already_covered": []}

    def update(self, lecture_id, section_json, summary, latex, topics):
        self.updates.append({"lecture_id": lecture_id, "summary": summary, "latex": latex, "topics": topics})
        return f"sec-{len(self.updates)}"

    def mark_questions_used(self, items, lecture_id):
        self.marked.append((items, lecture_id))


@pytest.fixture
def fake_llm(monkeypatch):
    def install(**kwargs):
        client = FakeLLMClient(**kwargs)
        monkeypatch.setattr("shared.llm.get_llm_client", lambda: client)
        return client
    return install


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    """Run in tmp_path so .pipeline_cache is created there, not in the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
