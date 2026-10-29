"""Generation writes worksheet JSON (no .tex). Mocked LLM: proves wiring, not model quality."""

import json
import re

import pytest

from conftest import FakeKB, ROOT
from generation.pipeline import run_generation_pipeline
from generation.stages import WriterOutput
from generation.worksheet import Worksheet
from shared.cache import PipelineCache
from shared.llm import LLMPipelineError

SECTIONS = [
    {
        "section_title": "1. Cosine Similarity",
        "section_content": "Cosine similarity compares vector directions.",
        "topics": ["cosine similarity"],
        "subtopics": ["vector space model"],
        "learning_objectives": ["Compute cosine similarity."],
        "key_misconceptions": ["Length matters"],
        "extracted_questions": [{"text": "What is cos 0?"}],
    },
    {
        "section_title": "2. TF-IDF",
        "section_content": "TF-IDF weighs terms.",
        "topics": ["tf-idf"],
        "subtopics": [],
        "learning_objectives": [],
        "key_misconceptions": [],
        "extracted_questions": [],
    },
]


def writer_reply(tag, worked=True, formal=None):
    return {
        "theory": {
            "motivation": f"Why {tag}.",
            "intuition": f"Idea of {tag}.",
            "formal_content": formal or f"$$f_{{{tag}}}(x) = x$$",
            "worked_example": (
                {"problem": "Compute $1+1$.", "steps": ["$1+1=2$"], "answer": "$2$", "insight": "Adding works."}
                if worked else None
            ),
            "key_takeaway": f"Remember {tag}.",
        },
        "notation": [{"symbol": "$x$", "meaning": "a number"}],
        "summary": f"Taught {tag}.",
    }


def question_reply(pyq=None, deferred=None):
    return {
        "practice": [
            {"level": "recall", "text": "State $f$.", "answer": "$f(x)=x$"},
            {"level": "apply", "text": "Compute $f(2)$.", "answer": "$2$"},
        ],
        "pyq": pyq or [],
        "deferred": deferred or [],
    }


def run(tmp, kb=None, out_name="L01.json", **kwargs):
    ped = tmp / "ped.json"
    ped.write_text(json.dumps(SECTIONS), encoding="utf-8")
    cache = PipelineCache(ped, kb_id="course.cmkb" if kb else None, lecture_id="L01", fresh=kwargs.pop("fresh", False))
    out = tmp / "out" / out_name
    result = run_generation_pipeline(
        pedagogical_json=SECTIONS, kb=kb, lecture_id="L01", output_path=out, cache=cache, **kwargs
    )
    return out, result, cache


def test_writes_valid_worksheet_json_and_no_tex(in_tmp, fake_llm):
    llm = fake_llm(
        writer_replies=[writer_reply("a"), writer_reply("b", worked=False)],
        question_replies=[
            question_reply(pyq=[{"id": "lec:0:0", "text": "What is cos 0?", "source": "lecture slide", "answer": "1"}]),
            question_reply(),
        ],
    )
    out, result, _ = run(in_tmp, is_objective=False, newpage_per_question=False)

    assert out.exists()
    assert not list(in_tmp.rglob("*.tex"))
    data = json.loads(out.read_text(encoding="utf-8"))
    ws = Worksheet.model_validate(data)
    assert result["worksheet"] == data
    assert result["summaries"] == ["Taught a.", "Taught b."]

    assert (data["schema_name"], data["schema_version"], data["content_format"]) == ("adhd-worksheet", 1, "markdown+tex")
    assert data["title"] == "L01" and data["lecture_id"] == "L01"
    assert data["render_hints"] == {"newpage_per_question": False}
    assert [s["index"] for s in data["sections"]] == [1, 2]

    s1 = ws.sections[0]
    assert s1.title == "1. Cosine Similarity"
    assert s1.topics == ["cosine similarity", "vector space model"]
    assert s1.learning_objectives == ["Compute cosine similarity."]
    assert s1.notation[0].symbol == "x"  # $ delimiters stripped
    assert s1.theory.worked_example.steps == ["$1+1=2$"]
    assert [q.number for q in s1.practice_questions] == [1, 2]
    assert [q.number for q in s1.past_year_questions] == [3]
    assert s1.past_year_questions[0].candidate_id == "lec:0:0"
    assert s1.summary == "Taught a."
    assert ws.sections[1].theory.worked_example is None

    # Call B gets the theory as plain text, not a JSON/LaTeX blob.
    q_prompt = [p for k, p in llm.calls if k == "questions"][0]
    assert "## Motivation\nWhy a." in q_prompt and "## Worked Example" in q_prompt
    assert "\\subsubsection" not in q_prompt

    # No LaTeX layout leaked into the output.
    raw = out.read_text(encoding="utf-8")
    assert "\\newpage" not in raw and "\\begin{question}" not in raw and "\\section" not in raw


def test_pyq_bookkeeping_and_memory_commit(in_tmp, fake_llm):
    kb = FakeKB(questions=[{
        "canonical_topic": "cosine similarity",
        "matches": [{"pk": 42, "source": "Endsem 2024", "qid": "3", "question": "Why cosine?", "answer": "length"}],
    }])
    fake_llm(
        writer_replies=[writer_reply("a"), writer_reply("b")],
        question_replies=[
            question_reply(pyq=[{"id": "kb:42", "text": "Why cosine?", "source": "Endsem 2024", "adapted": True, "answer": "length"}]),
            question_reply(deferred=[{"id": "def:x", "text": "Derive skip-gram.", "source": "Mid 2023", "reason": "not taught"}]),
        ],
    )
    out, _, cache = run(in_tmp, kb=kb)
    data = json.loads(out.read_text(encoding="utf-8"))

    pyq = data["sections"][0]["past_year_questions"][0]
    assert pyq["candidate_id"] == "kb:42" and pyq["adapted"] is True and pyq["source"] == "Endsem 2024"
    assert data["unplaced_questions"] == [{"text": "Derive skip-gram.", "source": "Mid 2023", "reason": "not taught"}]

    assert len(kb.updates) == 2
    stored = json.loads(kb.updates[0]["latex"])  # section worksheet JSON in the "latex" column
    assert stored["title"] == "1. Cosine Similarity" and stored["index"] == 1
    assert kb.marked == [([{"pk": 42, "exam": "Endsem 2024", "qid": "3", "action": "adapted"}], "L01")]
    assert cache.get_section_step(0, "memory_updated") is True
    assert cache.get_section_step(0, "compiled") is None


def test_resume_uses_cache_and_does_not_recommit(in_tmp, fake_llm):
    kb = FakeKB()
    fake_llm(writer_replies=[writer_reply("a"), writer_reply("b")], question_replies=[question_reply(), question_reply()])
    out, _, _ = run(in_tmp, kb=kb)
    first = json.loads(out.read_text(encoding="utf-8"))

    llm = fake_llm()  # no replies queued: any LLM call fails the test
    out2, _, _ = run(in_tmp, kb=kb)
    second = json.loads(out2.read_text(encoding="utf-8"))
    assert llm.calls == []
    assert len(kb.updates) == 2
    first.pop("generated_at"), second.pop("generated_at")
    assert first == second


def test_invalid_writer_output_raises_and_is_not_cached(in_tmp, fake_llm):
    legacy = {"theory": "\\subsubsection{Motivation} old LaTeX string", "notation": [], "summary": "x"}
    fake_llm(writer_replies=[legacy, legacy, legacy])
    with pytest.raises(LLMPipelineError):
        run(in_tmp)
    assert not (in_tmp / "out" / "L01.json").exists()
    ped = in_tmp / "ped.json"
    assert PipelineCache(ped, lecture_id="L01").get_section_step(0, "writer") is None


def test_structural_latex_triggers_repair(in_tmp, fake_llm):
    llm = fake_llm(
        writer_replies=[writer_reply("a", formal="\\section{Bad} text"), writer_reply("a"), writer_reply("b")],
        question_replies=[question_reply(), question_reply()],
    )
    out, _, _ = run(in_tmp)
    writer_prompts = [p for k, p in llm.calls if k == "writer"]
    assert len(writer_prompts) == 3
    assert "previous response was invalid" in writer_prompts[1] and "\\section" in writer_prompts[1]
    assert json.loads(out.read_text(encoding="utf-8"))["sections"][0]["theory"]["formal_content"] == "$$f_{a}(x) = x$$"


def test_writer_model_rejects_empty_parts():
    bad = writer_reply("a")
    bad["theory"]["intuition"] = ""
    with pytest.raises(Exception):
        WriterOutput.model_validate(bad)


def test_unescaped_backslash_is_rejected():
    good = writer_reply("a", formal=r"$\frac{1}{2}$")
    assert WriterOutput.model_validate(good).theory.formal_content == r"$\frac{1}{2}$"
    # A model writing "\frac" with ONE backslash in its JSON: json.loads turns \f into a form feed.
    raw = json.dumps(good).replace(r"\\frac", r"\frac")
    assert "\f" in json.loads(raw)["theory"]["formal_content"]
    with pytest.raises(Exception):
        WriterOutput.model_validate(json.loads(raw))


def test_schema_doc_example_validates():
    doc = (ROOT / "docs" / "WORKSHEET_JSON_SCHEMA.md").read_text(encoding="utf-8")
    block = re.search(r"```json\n(.*?)\n```", doc, re.S).group(1)
    Worksheet.model_validate(json.loads(block))
