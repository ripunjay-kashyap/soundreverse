# File-Upload Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace YouTube/yt-dlp ingestion with local mp3/wav upload to the Modal MCP, keeping 3 cached demo tracks that run instantly without Modal.

**Architecture:** A single new `mcp_node` (replacing `researcher` + `mcp_mock`) is the graph entry point. It branches: a *demo* loads a cached `SignalSignature` JSON; an *upload* streams the file to Modal's `/upload`, polls Modal's `/jobs/{id}`, and returns the same `raw_mcp_output` shape. Everything from the Gateway onward (gateway → musician → analyst → critic → output) is unchanged. The browser uploads a file to the backend, which is Modal's client.

**Tech Stack:** Python (LangGraph, FastAPI, Pydantic, requests, tenacity, pytest), React + Vite, Supabase.

**Spec:** `docs/superpowers/specs/2026-05-23-file-upload-pivot-design.md`

**Commits:** No `Co-Authored-By` trailer (project convention). Work on branch `feature/file-upload-pivot`.

---

## File Structure

- **Create** `agents/mcp.py` — the new `mcp_node` (demo loader + Modal upload/poll client).
- **Create** `tests/test_mcp.py` — unit tests for the demo branch, upload branch (mocked HTTP), and failure handling.
- **Modify** `agents/graph.py` — entry point, `GraphState` fields, `run()` signature, CLI.
- **Modify** `api.py` — `/analyze` (multipart), `/demo`, unified worker, 300s timeout, 3 demo tracks, result payload.
- **Create** `tests/test_api.py` — validation tests for `/analyze` and `/demo`.
- **Modify** `frontend/src/App.jsx` — remove search bar, wire upload + demo, request logic, loader copy.
- **Modify** `frontend/src/components/AnalyzeButton.jsx` — accept a `disabled` prop.
- **Modify** `frontend/vite.config.js` — proxy `/demo`.
- **Modify** `requirements.txt` — remove `yt-dlp`, add `requests`.
- **Delete** `agents/researcher.py`, `agents/mcp_mock.py`, `tests/test_researcher.py`.
- **Modify** `CLAUDE.md` — reflect the upload pipeline.
- **Manual** `.env` — add `MODAL_MCP_URL` (user action; cannot be automated).

---

## Task 1: Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Swap yt-dlp for requests**

In `requirements.txt`, remove the line `yt-dlp>=2024.0.0` and add `requests>=2.31.0`. Final file:

```
langgraph>=0.2.0
langchain-google-genai>=2.0.0
langchain-core>=0.3.0
langsmith>=0.1.0
pydantic>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
fpdf2>=2.7.0
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
tenacity>=8.0.0
pytest>=8.0.0
requests>=2.31.0
supabase>=2.0.0
```

- [ ] **Step 2: Install**

Run: `venv/Scripts/python -m pip install -r requirements.txt`
Expected: installs `requests` (already present transitively; confirms no `yt-dlp` needed).

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: drop yt-dlp, add requests for Modal client"
```

---

## Task 2: The `mcp_node` (demo + Modal upload)

**Files:**
- Create: `agents/mcp.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python -m pytest tests/test_mcp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.mcp'`.

- [ ] **Step 3: Implement `agents/mcp.py`**

```python
import json
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

if TYPE_CHECKING:
    from agents.graph import GraphState

CACHE_DIR = Path(__file__).parent.parent / "cache"

POLL_INTERVAL_S = 3.0
POLL_DEADLINE_S = 250.0          # stay under api.py's 300s worker timeout
SIGNATURE_KEYS = ("master", "stems", "rhythm")


def _modal_base() -> str:
    return os.getenv("MODAL_MCP_URL", "").rstrip("/")


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return text or "uploaded_track"


def _extract_signature(payload: dict) -> dict | None:
    """Return the SignalSignature dict from a Modal poll response, or None if not ready yet."""
    if not isinstance(payload, dict):
        return None
    for candidate in (payload, payload.get("result"), payload.get("signature")):
        if isinstance(candidate, dict) and all(k in candidate for k in SIGNATURE_KEYS):
            return candidate
    return None


def _is_failed(payload: dict) -> bool:
    status = (payload.get("status") or "").lower() if isinstance(payload, dict) else ""
    return status in {"failed", "error"}


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _modal_upload(audio_path: str, filename: str) -> str:
    """POST raw audio bytes to Modal /upload; return Modal's job id."""
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{_modal_base()}/upload",
            data=f,
            headers={"X-Filename": filename},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["job_id"]


def _modal_poll(modal_job_id: str) -> dict:
    """Poll Modal /jobs/{id} until the SignalSignature is ready; raise on failure/timeout."""
    deadline = time.monotonic() + POLL_DEADLINE_S
    while time.monotonic() < deadline:
        resp = requests.get(f"{_modal_base()}/jobs/{modal_job_id}", timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if _is_failed(payload):
            raise RuntimeError(payload.get("error") or "Modal analysis failed.")
        sig = _extract_signature(payload)
        if sig is not None:
            return sig
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError("Modal analysis did not complete within the polling deadline.")


def _analyze_upload(audio_path: str, filename: str) -> dict:
    if not _modal_base():
        raise RuntimeError("MODAL_MCP_URL is not configured.")
    modal_job_id = _modal_upload(audio_path, filename)
    sig = _modal_poll(modal_job_id)
    title = Path(filename).stem
    sig.setdefault("metadata", {})
    sig["metadata"].setdefault("title", title)
    sig["metadata"].setdefault("artist", "")
    sig["track_id"] = _slugify(title)
    return sig


def _load_demo(track_id: str) -> dict:
    return json.loads((CACHE_DIR / f"{track_id}.json").read_text(encoding="utf-8"))


def mcp_node(state: "GraphState") -> "GraphState":
    """Entry node: produce raw_mcp_output from a cached demo or a real Modal analysis."""
    if state.get("error"):
        return state

    demo_track_id = state.get("demo_track_id")
    audio_path = state.get("audio_path")
    try:
        if demo_track_id:
            data = _load_demo(demo_track_id)
            track_id = data.get("track_id", demo_track_id)
        elif audio_path:
            filename = state.get("audio_filename") or Path(audio_path).name
            data = _analyze_upload(audio_path, filename)
            track_id = data["track_id"]
        else:
            return {**state, "error": "No demo_track_id or audio_path provided to MCP.", "final": True}
        return {**state, "raw_mcp_output": data, "_track_id": track_id}
    except Exception as e:
        return {**state, "error": f"MCP analysis failed: {e}", "final": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python -m pytest tests/test_mcp.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/mcp.py tests/test_mcp.py
git commit -m "feat: add mcp_node (cached demo + Modal upload/poll)"
```

---

## Task 3: Rewire the graph, remove the YouTube nodes

**Files:**
- Modify: `agents/graph.py`
- Delete: `agents/researcher.py`, `agents/mcp_mock.py`, `tests/test_researcher.py`

- [ ] **Step 1: Update imports in `agents/graph.py`**

Replace these lines:

```python
from agents.researcher import researcher_node
from agents.mcp_mock import mcp_mock_node
```

with:

```python
from agents.mcp import mcp_node
```

- [ ] **Step 2: Update `GraphState`**

In the `GraphState` TypedDict, remove `user_input`, `youtube_url`, `researcher_metadata` and add the upload fields. The class becomes:

```python
class GraphState(TypedDict):
    audio_path:        str | None
    audio_filename:    str | None
    demo_track_id:     str | None
    raw_mcp_output:    dict | None
    track_request:     TrackRequest | None
    signal_signature:  SignalSignature | None
    musician_notes:    MusicianNotes | None
    producer_settings: ProducerSettings | None
    iteration_count:   int
    confidence:        float
    critique:          str
    critique_history:  list[str]
    critic_rounds:     list[dict]
    validation_checks: list[dict]
    final:             bool
    error:             str | None
    trace_url:         str | None
    stress_test:       bool
    _track_id:         str
    job_id:            str | None
```

- [ ] **Step 3: Update `build_graph()`**

Replace the node registration + entry + first edges. The function body becomes:

```python
def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("mcp", mcp_node)
    graph.add_node("gateway", gateway_node)
    graph.add_node("musician", musician_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("mcp")
    graph.add_edge("mcp", "gateway")
    graph.add_edge("gateway", "musician")
    graph.add_edge("musician", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {
        "analyst": "analyst",
        "output": END,
    })

    return graph.compile()
```

- [ ] **Step 4: Update `run()` signature and initial state**

Replace the `run(...)` definition down to `final_state = app.invoke(...)`:

```python
def run(
    audio_path: str | None = None,
    audio_filename: str | None = None,
    demo_track_id: str | None = None,
    stress_test: bool = False,
    job_id: str | None = None,
) -> dict:
    app = build_graph()

    initial_state: GraphState = {
        "audio_path": audio_path,
        "audio_filename": audio_filename,
        "demo_track_id": demo_track_id,
        "raw_mcp_output": None,
        "_track_id": "",
        "track_request": None,
        "signal_signature": None,
        "musician_notes": None,
        "producer_settings": None,
        "iteration_count": 0,
        "confidence": 0.0,
        "critique": "",
        "critique_history": [],
        "critic_rounds": [],
        "validation_checks": [],
        "final": False,
        "error": None,
        "trace_url": None,
        "stress_test": stress_test,
        "job_id": job_id,
    }

    project = os.environ.get("LANGSMITH_PROJECT", "soundreverse-v1")
    tracer = LangChainTracer(project_name=project)

    final_state = app.invoke(initial_state, config={"callbacks": [tracer]})
```

(Leave everything after `app.invoke(...)` — trace capture, `output_node`, printing — unchanged.)

- [ ] **Step 5: Update the CLI `__main__` block**

Replace the argparse block at the bottom:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SoundReverse — Producer Session Pack generator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", help="Demo track id (e.g. billie_jean_mj)")
    group.add_argument("--file", help="Path to a local mp3/wav file")
    args = parser.parse_args()

    if args.demo:
        run(demo_track_id=args.demo)
    else:
        run(audio_path=args.file, audio_filename=Path(args.file).name)
```

- [ ] **Step 6: Delete the dead YouTube modules and test**

```bash
git rm agents/researcher.py agents/mcp_mock.py tests/test_researcher.py
```

- [ ] **Step 7: Verify the graph compiles and the demo path still works end-to-end (no LLM mock needed for compile)**

Run: `venv/Scripts/python -c "import sys; sys.path.insert(0,'.'); from agents.graph import build_graph; build_graph(); print('OK')"`
Expected: prints `OK` (no import errors for researcher/mcp_mock).

Run: `venv/Scripts/python -m pytest tests/ -v`
Expected: PASS — `test_researcher.py` is gone; `test_mcp.py`, `test_gateway.py`, `test_analyst_rules.py`, `test_critic.py`, `test_output.py`, `test_mcp_contract.py` collected and passing.

- [ ] **Step 8: Commit**

```bash
git add agents/graph.py
git commit -m "feat: make mcp the graph entry point; remove researcher + mcp_mock"
```

---

## Task 4: API — upload + demo endpoints

**Files:**
- Modify: `api.py`

- [ ] **Step 1: Update imports and constants**

Add to the FastAPI imports near the top of `api.py`:

```python
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
```

Below `OUTPUT_DIR` setup, add an upload temp dir and limits:

```python
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).parent / "tmp")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024            # 50 MB
ALLOWED_EXTS = {".mp3", ".wav"}
```

- [ ] **Step 2: Reduce demo registry to 3 tracks**

Replace `TRACKS`:

```python
TRACKS = [
    {"track_id": "billie_jean_mj",        "label": "Billie Jean — Michael Jackson", "stress_test": False},
    {"track_id": "humble_kendrick",       "label": "HUMBLE. — Kendrick Lamar",      "stress_test": True},
    {"track_id": "blinding_lights_weeknd", "label": "Blinding Lights — The Weeknd",  "stress_test": False},
]
TRACKS_BY_ID = {t["track_id"]: t for t in TRACKS}
```

- [ ] **Step 3: Replace the request model and unify the worker**

Replace `class AnalyzeRequest` with:

```python
class DemoRequest(BaseModel):
    track_id: str
```

Replace `_run_job(...)` with a unified worker that handles both paths and cleans up the temp file:

```python
async def _run_job(
    job_id: str,
    api_base: str,
    *,
    audio_path: str | None = None,
    audio_filename: str | None = None,
    demo_track_id: str | None = None,
    stress_test: bool = False,
) -> None:
    sb = get_supabase()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({"status": "processing", "updated_at": now_iso}).eq("id", job_id).execute()

        state = await asyncio.wait_for(
            asyncio.to_thread(
                run_graph,
                audio_path,
                audio_filename,
                demo_track_id,
                stress_test,
                job_id,
            ),
            timeout=300.0,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        if state.get("error"):
            sb.table("jobs").update({
                "status": "failed", "error_message": state["error"], "updated_at": now_iso
            }).eq("id", job_id).execute()
            return

        sb.table("jobs").update({
            "status": "completed",
            "result_payload": _build_result_payload(state, api_base),
            "updated_at": now_iso,
        }).eq("id", job_id).execute()

    except asyncio.TimeoutError:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({
            "status": "failed", "error_message": "Analysis timed out after 300 seconds.", "updated_at": now_iso
        }).eq("id", job_id).execute()
    except Exception as exc:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({
            "status": "failed", "error_message": str(exc), "updated_at": now_iso
        }).eq("id", job_id).execute()
    finally:
        if audio_path:
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception as e:
                print(f"[Upload cleanup] Failed to delete {audio_path}: {e}")
```

Note: `run_graph` is called positionally as `(audio_path, audio_filename, demo_track_id, stress_test, job_id)` — matching the new `run()` signature from Task 3.

- [ ] **Step 4: Replace the `/analyze` endpoint and add `/demo`**

Replace the existing `@app.post("/analyze", ...)` function with these two:

```python
@app.post("/analyze", status_code=202)
async def analyze(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload an mp3 or wav.")

    job_id = str(uuid.uuid4())
    audio_path = UPLOAD_DIR / f"{job_id}_input{ext}"

    # Stream to disk in chunks; enforce the size cap without buffering the whole file.
    size = 0
    with open(audio_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                audio_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large. Max 50 MB.")
            out.write(chunk)

    sb = get_supabase()
    sb.table("jobs").insert({
        "id": job_id, "status": "pending", "user_input": file.filename, "stress_test": False,
    }).execute()

    api_base = os.getenv("API_BASE_URL", "")
    background_tasks.add_task(
        _run_job, job_id, api_base,
        audio_path=str(audio_path), audio_filename=file.filename, stress_test=False,
    )
    return {"job_id": job_id}


@app.post("/demo", status_code=202)
async def demo(req: DemoRequest, background_tasks: BackgroundTasks):
    track = TRACKS_BY_ID.get(req.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail=f"Unknown demo track: {req.track_id}")

    job_id = str(uuid.uuid4())
    stress_test = track["stress_test"]

    sb = get_supabase()
    sb.table("jobs").insert({
        "id": job_id, "status": "pending", "user_input": req.track_id, "stress_test": stress_test,
    }).execute()

    api_base = os.getenv("API_BASE_URL", "")
    background_tasks.add_task(
        _run_job, job_id, api_base,
        demo_track_id=req.track_id, stress_test=stress_test,
    )
    return {"job_id": job_id}
```

- [ ] **Step 5: Clean YouTube fields from the result payload**

In `_build_result_payload`, remove `youtube_url` from the `track` block and `researcher_reasoning` from `pipeline`, and drop the now-unused `researcher_meta`. The `track` and `pipeline` blocks become:

```python
    return {
        "track": {
            "title":  meta.get("title", track_id),
            "artist": meta.get("artist", ""),
            "lufs":   sig.master.lufs if sig else None,
            "bpm":    sig.rhythm.bpm if sig else None,
            "key":    sig.rhythm.key if sig else None,
        },
        "pipeline": {
            "confidence":        state["confidence"],
            "iteration_count":   state["iteration_count"],
            "max_iterations":    3,
            "critic_rounds":     state.get("critic_rounds", []),
            "validation_checks": state.get("validation_checks", []),
        },
        "settings":  settings.model_dump() if settings else None,
        "musician":  musician_notes.model_dump() if musician_notes else None,
        "trace_url": state.get("trace_url"),
        "outputs": {
            "pdf_url":      f"{api_base}/outputs/{prefix}_blueprint.pdf",
            "json_url":     f"{api_base}/outputs/{prefix}_preset.json",
            "metadata_url": f"{api_base}/outputs/{prefix}_metadata.json",
        },
    }
```

Also remove the line `researcher_meta = state.get("researcher_metadata", {})` near the top of `_build_result_payload` (it is no longer referenced).

- [ ] **Step 6: Smoke-check the app imports**

Run: `venv/Scripts/python -c "import sys; sys.path.insert(0,'.'); import api; print('OK')"`
Expected: prints `OK` (no NameError from leftover `AnalyzeRequest`/`researcher_metadata`).

- [ ] **Step 7: Commit**

```bash
git add api.py
git commit -m "feat: /analyze accepts file upload, add /demo, 300s timeout, 3 demos"
```

---

## Task 5: API validation tests

**Files:**
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

These exercise the synchronous validation paths (which run before the background task), with Supabase stubbed so no network/DB is touched.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Stub the Supabase client so insert/update are no-ops.
    class _Q:
        def insert(self, *a, **k): return self
        def update(self, *a, **k): return self
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def or_(self, *a, **k): return self
        def single(self): return self
        def execute(self): 
            class R: data = []
            return R()
    class _SB:
        def table(self, *a, **k): return _Q()

    import utils.supabase_client as sc
    monkeypatch.setattr(sc, "get_supabase", lambda: _SB())
    import api
    monkeypatch.setattr(api, "get_supabase", lambda: _SB())
    return TestClient(api.app)


def test_analyze_rejects_non_audio(client):
    resp = client.post("/analyze", files={"file": ("notes.txt", io.BytesIO(b"hi"), "text/plain")})
    assert resp.status_code == 415


def test_analyze_accepts_mp3(client):
    resp = client.post("/analyze", files={"file": ("song.mp3", io.BytesIO(b"\x00\x01\x02"), "audio/mpeg")})
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_demo_unknown_track_404(client):
    resp = client.post("/demo", json={"track_id": "not_a_real_track"})
    assert resp.status_code == 404


def test_demo_known_track_202(client):
    resp = client.post("/demo", json={"track_id": "billie_jean_mj"})
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_tracks_returns_three(client):
    resp = client.get("/tracks")
    assert resp.status_code == 200
    assert len(resp.json()) == 3
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS (5 tests). Background tasks may attempt to run after the response; they are harmless because the stubbed Supabase swallows writes and `run_graph` for `/analyze` will fail-and-cleanup on the tiny fake file (the test only asserts the 202 + job_id returned synchronously).

> If a background task error is noisy in test output, it does not fail the assertions. To silence it, this is acceptable to leave as-is.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add /analyze and /demo validation tests"
```

---

## Task 6: Frontend — upload primary, demo secondary

**Files:**
- Modify: `frontend/src/components/AnalyzeButton.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Add a `disabled` prop to `AnalyzeButton`**

Replace the component signature/usage in `frontend/src/components/AnalyzeButton.jsx`:

```jsx
export default function AnalyzeButton({ loading, disabled, onClick }) {
  return (
    <button className="analyze-btn" onClick={onClick} disabled={loading || disabled}>
      {loading ? (
        <>
          <Spinner />
          Analyzing…
        </>
      ) : (
        'Run Analysis'
      )}
    </button>
  )
}
```

(Leave the `Spinner` function unchanged.)

- [ ] **Step 2: Add `/demo` to the Vite proxy**

In `frontend/vite.config.js`, add a `/demo` entry to `server.proxy`:

```js
    proxy: {
      '/analyze': 'http://127.0.0.1:8001',
      '/demo':    'http://127.0.0.1:8001',
      '/tracks':  'http://127.0.0.1:8001',
      '/outputs': 'http://127.0.0.1:8001',
      '/jobs':    'http://127.0.0.1:8001',
    },
```

- [ ] **Step 3: Rework `App.jsx` state + request logic**

In `frontend/src/App.jsx`, replace the `selectedTrack` state and `handleAnalyze` with upload + demo handling.

Replace:
```jsx
  const [selectedTrack, setSelectedTrack] = useState('')
```
with:
```jsx
  const [uploadedFile, setUploadedFile] = useState(null)
  const [selectedDemo, setSelectedDemo] = useState('')
```

Also fix the `/tracks` `useEffect`, which currently calls the now-removed `setSelectedTrack`. Change its `.then` so it only stores the list (no auto-select — upload stays the default action):

```jsx
    fetch(`${API_BASE}/tracks`)
      .then(r => r.json())
      .then(data => setTracks(data))
      .catch(() => setError('Failed to load tracks'))
```

Replace the entire `async function handleAnalyze() { ... }` with:

```jsx
  // Shared polling loop: given a job_id, resolve with the result or reject on failure.
  function pollJob(jobId) {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const poll = await fetch(`${API_BASE}/jobs/${jobId}`)
          if (!poll.ok) { clearInterval(interval); reject(new Error(`Poll error ${poll.status}`)); return }
          const job = await poll.json()
          if (job.status === 'completed') { clearInterval(interval); resolve(job.result) }
          else if (job.status === 'failed') { clearInterval(interval); reject(new Error(job.error || 'Job failed')) }
        } catch (e) { clearInterval(interval); reject(e) }
      }, 3000)
    })
  }

  async function submit(makeRequest) {
    setLoading(true); setResult(null); setError(null)
    try {
      const res = await makeRequest()
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const { job_id } = await res.json()
      const data = await pollJob(job_id)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleAnalyze() {
    if (uploadedFile) {
      const fd = new FormData()
      fd.append('file', uploadedFile)
      submit(() => fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd }))
    } else if (selectedDemo) {
      submit(() => fetch(`${API_BASE}/demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_id: selectedDemo }),
      }))
    }
  }
```

- [ ] **Step 4: Replace the sidebar input markup**

In `App.jsx`, replace the block that starts at `<p className="eyebrow" ...>Search Track</p>` and ends at the closing of the `TrackSelector` line — i.e. the `search-bar`, the "Or Upload a Track" eyebrow, the `<FileUpload />`, the "Or Select Cached" eyebrow, and the `<TrackSelector ... />` — with:

```jsx
          <p className="eyebrow" style={{ marginBottom: 12, paddingLeft: 4 }}>Upload Your Track</p>
          <div style={{ marginBottom: 22 }}>
            <FileUpload onFileChange={setUploadedFile} />
          </div>

          <p className="eyebrow" style={{ marginBottom: 12, paddingLeft: 4 }}>Or Try a Demo</p>
          <TrackSelector tracks={tracks} selected={selectedDemo} onChange={setSelectedDemo} />
```

- [ ] **Step 5: Update the AnalyzeButton usage and loader label**

Replace the `<AnalyzeButton ... />` usage with:

```jsx
          <AnalyzeButton
            loading={loading}
            disabled={!uploadedFile && !selectedDemo}
            onClick={handleAnalyze}
          />
```

Replace the `LoadingState` label lookup (currently `tracks.find(t => t.track_id === selectedTrack)?.label || selectedTrack`) with a label that works for both paths:

```jsx
          <LoadingState label={uploadedFile ? uploadedFile.name : (tracks.find(t => t.track_id === selectedDemo)?.label || '')} />
```

In `LoadingState`, change the caption `This can take up to a minute — hang tight and keep this tab open.` to `This can take up to ~90 seconds — hang tight and keep this tab open.`

- [ ] **Step 6: Verify the dev build compiles**

Start (or rely on the running) Vite dev server and confirm a clean HMR/compile.
Run: `cd frontend; npm run build`
Expected: build completes with no errors (no references to `selectedTrack`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/AnalyzeButton.jsx frontend/vite.config.js
git commit -m "feat(ui): upload-primary input with demo tracks; remove YouTube search"
```

---

## Task 7: Config + docs

**Files:**
- Modify: `CLAUDE.md`
- Manual: `.env` (user action)

- [ ] **Step 1: Tell the user to add the Modal URL to `.env`**

`.env` cannot be edited programmatically (gitignored / secrets). Instruct the user to add:

```
MODAL_MCP_URL=https://ripun-j-kashyap--audio-sonic-mcp-mcp-server.modal.run
```

- [ ] **Step 2: Update `CLAUDE.md`**

Apply these edits so the doc matches the new pipeline:
- **"What This Project Is":** change the opening to: takes an **uploaded mp3/wav** (or a cached demo track), the **MCP step** (Modal, real) produces the `SignalSignature`, and the Gateway → Musician → Analyst → Critic loop turns it into producer settings. Remove the Researcher/YouTube sentence.
- **Project Structure:** remove `researcher.py` and `mcp_mock.py`; add `mcp.py ← demo loader + Modal /upload client (real audio analysis)`. Update the `graph.py` orchestration line to `mcp→gateway→musician→analyst→critic`. Update `tests/` line (remove `researcher`; add `mcp`, `api`).
- **Tech Stack:** replace the `yt-dlp` "Song search" bullet with `Audio in: local mp3/wav upload → Modal MCP /upload (binary POST), poll /jobs/{id}`. Drop `yt-dlp`; add `requests`. Remove `MODEL ... researcher.py` mention of researcher.
- **Flow diagram:** `Upload/Demo → MCP (Modal/cache) → Gateway → Musician → Analyst → Critic → OUTPUT`.
- Replace the **Researcher Agent** section with an **MCP Node (`agents/mcp.py`)** section: demo branch loads `cache/{track_id}.json`; upload branch POSTs bytes to `${MODAL_MCP_URL}/upload` (`X-Filename`), polls `/jobs/{id}` until the signature is ready; on failure sets `error`. Modal status vocab is `"success"`.
- **API Contract:** `POST /analyze` is now `multipart/form-data` (`file`); add `POST /demo {track_id}`; `GET /tracks` returns 3 demos; remove `youtube_url` and `researcher_reasoning` from the `GET /jobs` example.
- **GraphState** list: remove `user_input`/`youtube_url`/`researcher_metadata`; add `audio_path`/`audio_filename`/`demo_track_id`.
- **Common Commands:** change CLI to `python -m agents.graph --demo humble_kendrick` and `python -m agents.graph --file path/to/song.mp3`.
- **What Claude Should Never Do:** remove the YouTube/Researcher items if any; add "Don't reintroduce yt-dlp/YouTube ingestion (datacenter IPs are bot-blocked; see the file-upload spec)".

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for the file-upload pipeline"
```

---

## Task 8: End-to-end manual verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm `.env` has `MODAL_MCP_URL`** and the Modal server is deployed/reachable.

- [ ] **Step 2: Start backend + frontend**

Run (backend): `venv/Scripts/python -m uvicorn api:app --port 8001`
Run (frontend): `cd frontend; npm run dev`

- [ ] **Step 3: Demo path (no Modal)**

In the browser, pick a demo track → Run Analysis → expect a completed Producer Session Pack (musician notes, EQ, confidence, downloads) in a few seconds.

- [ ] **Step 4: Upload path (real Modal)**

Upload a local mp3/wav → Run Analysis → expect a completed pack in ~70–95s (longer on a cold Modal container). Confirm the title shows the filename and the downloads work.

- [ ] **Step 5: Error path**

Upload with the backend's `MODAL_MCP_URL` unset (or a bad URL) → expect the job to fail with a clear "MCP analysis failed" message, and the temp file under `tmp/` to be deleted.

- [ ] **Step 6: Full test suite**

Run: `venv/Scripts/python -m pytest tests/ -v`
Expected: all tests pass.

---

## Self-Review notes (addressed)

- **Spec coverage:** demo + upload paths (Tasks 2–4, 6), 3 demos (Task 4), Gateway-onward untouched (Task 3), error table (Tasks 2/4 + Task 8 step 5), testing (Tasks 2, 5), config/docs (Task 7), removals (Tasks 1, 3). Live-progress + S3 remain out of scope per spec.
- **`run()` arg order** is defined in Task 3 Step 4 and called positionally in Task 4 Step 3 — they match: `(audio_path, audio_filename, demo_track_id, stress_test, job_id)`.
- **Open items** (Modal in-progress poll shape, auth, metadata) are handled defensively in `_extract_signature`/`_is_failed` (Task 2) and the filename-title fallback (`_analyze_upload`); confirm with the Modal agent during Task 8.
