"""CLI --out handling and the API worksheet download. Pipelines are stubbed."""

import json
import sys
from pathlib import Path

import pytest

import main_cli


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["main_cli.py"] + argv)
    main_cli.main()


def test_out_must_be_json(in_tmp, monkeypatch):
    called = []
    monkeypatch.setattr(main_cli, "run_generation_pipeline", lambda **kw: called.append(kw))
    (in_tmp / "ped.json").write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        _run_cli(monkeypatch, ["generate", "ped.json", "--out", "w.tex"])
    assert e.value.code == 2 and called == []


def test_generate_refuses_to_overwrite_input(in_tmp, monkeypatch):
    monkeypatch.setattr(main_cli, "run_generation_pipeline", lambda **kw: None)
    (in_tmp / "ped.json").write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        _run_cli(monkeypatch, ["generate", "ped.json", "--out", "ped.json"])
    assert e.value.code == 2


def test_run_writes_pedagogy_next_to_worksheet(in_tmp, monkeypatch):
    seen = {}
    monkeypatch.setattr(main_cli, "run_extraction_pipeline", lambda **kw: seen.update(extract=kw) or [])
    monkeypatch.setattr(main_cli, "run_generation_pipeline", lambda **kw: seen.update(generate=kw))
    (in_tmp / "L01.pdf").write_bytes(b"%PDF-1.4 stub")
    _run_cli(monkeypatch, ["run", "L01.pdf", "--out", "out/L01.json", "--no-newpage"])
    assert seen["extract"]["output_json_path"] == Path("out/L01.pedagogy.json")
    assert seen["generate"]["output_path"] == Path("out/L01.json")
    assert seen["generate"]["newpage_per_question"] is False


def test_api_generate_and_download_worksheet(in_tmp, monkeypatch):
    from fastapi.testclient import TestClient
    import api.server as server

    def fake_pipeline(**kw):
        out = kw["output_path"]
        out.write_text(json.dumps({"schema_name": "adhd-worksheet"}), encoding="utf-8")
        server.log.info("Generation complete! Worksheet JSON saved to: %s", out)

    monkeypatch.setattr(server, "run_generation_pipeline", fake_pipeline)
    client = TestClient(server.app)
    sid = client.post("/api/sessions").json()["session_id"]
    try:
        r = client.post(f"/api/sessions/{sid}/extract", data={"lecture_id": "L01", "json_text": "[]"})
        assert r.status_code == 200

        assert client.get(f"/api/sessions/{sid}/download/worksheet").status_code == 404  # not generated yet

        body = client.get(f"/api/sessions/{sid}/generate").text
        assert "Generation complete" in body and "ERROR" not in body

        r = client.get(f"/api/sessions/{sid}/download/worksheet")
        assert r.status_code == 200
        assert r.json() == {"schema_name": "adhd-worksheet"}
        assert "L01_worksheet.json" in r.headers.get("content-disposition", "")

        assert client.get(f"/api/sessions/{sid}/download/tex").status_code == 400
    finally:
        client.delete(f"/api/sessions/{sid}")
