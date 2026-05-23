import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import agents.mcp as mcp

CACHE_DIR = Path(__file__).parent.parent / "cache"
BASE_STATE = {"error": None, "raw_mcp_output": None, "_track_id": ""}


def _valid_signature() -> dict:
    return json.loads((CACHE_DIR / "billie_jean_mj.json").read_text(encoding="utf-8"))


def test_demo_branch_loads_cache():
    state = mcp.mcp_node({**BASE_STATE, "demo_track_id": "clocks_coldplay",
                          "audio_path": None, "audio_filename": None})
    assert state["error"] is None
    assert state["raw_mcp_output"]["track_id"] == "clocks_coldplay"
    assert state["_track_id"] == "clocks_coldplay"


def test_extract_signature_detects_shape():
    assert mcp._extract_signature({"status": "processing"}) is None
    sig = _valid_signature()
    assert mcp._extract_signature(sig) is not None


def test_upload_branch_posts_and_polls(monkeypatch):
    monkeypatch.setenv("MODAL_MCP_URL", "https://fake.modal.run")
    sig = _valid_signature()
    calls = {"uploaded": False}

    def fake_upload(path, filename):
        calls["uploaded"] = True
        assert filename == "My Track.mp3"
        return "file_test123"

    def fake_poll(job_id):
        assert job_id == "file_test123"
        return sig

    monkeypatch.setattr(mcp, "_modal_upload", fake_upload)
    monkeypatch.setattr(mcp, "_modal_poll", fake_poll)

    state = mcp.mcp_node({**BASE_STATE, "demo_track_id": None,
                          "audio_path": "/tmp/whatever.mp3", "audio_filename": "My Track.mp3"})
    assert calls["uploaded"] is True
    assert state["error"] is None
    assert state["raw_mcp_output"]["metadata"]["title"] == "My Track"
    assert state["_track_id"] == "my_track"


def test_upload_branch_modal_failure_sets_error(monkeypatch):
    monkeypatch.setenv("MODAL_MCP_URL", "https://fake.modal.run")

    def fake_upload(path, filename):
        return "file_x"

    def fake_poll(job_id):
        raise RuntimeError("Modal analysis failed.")

    monkeypatch.setattr(mcp, "_modal_upload", fake_upload)
    monkeypatch.setattr(mcp, "_modal_poll", fake_poll)

    state = mcp.mcp_node({**BASE_STATE, "demo_track_id": None,
                          "audio_path": "/tmp/x.mp3", "audio_filename": "x.mp3"})
    assert state["error"] is not None
    assert "Modal analysis failed" in state["error"]
    assert state["final"] is True


def test_no_input_sets_error():
    state = mcp.mcp_node({**BASE_STATE, "demo_track_id": None,
                          "audio_path": None, "audio_filename": None})
    assert state["error"] is not None
    assert state["final"] is True
