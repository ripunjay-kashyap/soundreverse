# Design: File-Upload Pivot (remove YouTube)

**Date:** 2026-05-23
**Status:** Approved design — pending spec review → implementation plan

## Problem

The Researcher agent and the real Modal MCP both depend on `yt-dlp` against YouTube. After
deployment, requests originate from datacenter IPs (Render, Modal), which YouTube blocks with
`"Sign in to confirm you're not a bot"`. Cookies were tried on Modal and still failed; a paid
residential proxy is deferred to V2.

**Decision:** Remove the entire YouTube/online system. Input becomes a **local audio file
upload (mp3/wav)** sent to the Modal GPU MCP, which already runs the real Demucs/CLAP analysis
and returns a `SignalSignature`. Three pre-computed demo tracks remain for an instant, zero-cost
showcase.

## Goals / Non-goals

**Goals**
- Replace YouTube resolution + download with file upload → Modal analysis.
- Keep 3 cached demo tracks that run instantly without Modal.
- Preserve the existing reasoning pipeline (Gateway → Musician → Analyst → Critic → Output) and
  LangSmith tracing unchanged.

**Non-goals (deferred)**
- Paid residential proxy / any YouTube ingestion (V2).
- Wiring Modal's *real* per-stage progress into the loader — keep the current timer-based
  captions for now (V2).
- S3/R2 presigned-URL transport (Solution 1) — we use direct binary POST (Solution 2).

## Modal MCP contract (Solution 2 — direct binary POST)

```python
# Upload — raw bytes in body, filename in header
POST {MODAL_MCP_URL}/upload
  body    = raw file bytes
  headers = { "X-Filename": "track.mp3" }
  → { "job_id": "file_abc123" }

# Poll until success — returns the full SignalSignature JSON when done
GET {MODAL_MCP_URL}/jobs/file_abc123
  → SignalSignature JSON (on success)
```

- Modal status vocabulary is **`"success"`** (distinct from our Supabase `"completed"`).
- Modal job ids are **`file_`-prefixed** — no collision with our UUID job ids.
- Example shows **no auth**; routes treated as open. **OPEN ITEM:** add a token header if Modal
  later requires one.
- Modal GPU worker `timeout=600`, so cold starts are covered on Modal's side.
- **OPEN ITEM (confirm with Modal agent):** the exact shape of an *in-progress* poll response
  (e.g. `{"status": "processing"}`). Implementation will treat the job as done when the response
  carries the signature keys (`master`/`stems`/`rhythm`) or `status == "success"`, as failed on
  `status in {"failed","error"}`, and otherwise keep polling.

## Architecture & data flow

Both entry paths converge on the same `raw_mcp_output → Gateway` contract (the documented swap
point), so everything from the Gateway onward is untouched.

```
DEMO:    POST /demo {track_id}  ─┐
                                 ├─► Supabase job ─► graph: mcp ─► gateway ─► musician ─► analyst ⇄ critic ─► output
UPLOAD:  POST /analyze (file)  ──┘                       │
                                                         ├─ demo   → load cache/{track_id}.json
                                                         └─ upload → POST file to Modal /upload, poll /jobs/{id}
```

The browser only ever talks to our backend. `mcp_node` is Modal's client.

### Upload path (step by step)
1. Browser: user selects mp3/wav in `FileUpload`, clicks **Analyze** → `POST /analyze`
   (`multipart/form-data`, field `file`).
2. `api.py /analyze`: validate type (mp3/wav) + size (≤50 MB); **stream** to a temp file
   `tmp/{job_id}_input.<ext>` (no full in-memory buffering); insert Supabase job (`pending`);
   schedule `_run_job(job_id, audio_path, filename)`; return `{job_id}`.
3. Worker `_run_job`: job → `processing`; invoke graph with initial state
   `{audio_path, audio_filename, demo_track_id: None, job_id, stress_test: False}` under a **300s**
   timeout (`asyncio.to_thread`).
4. `mcp_node` (upload branch): stream bytes → `POST {MODAL_MCP_URL}/upload` with `X-Filename`
   → Modal `job_id`; poll `GET {MODAL_MCP_URL}/jobs/{id}` (~3s interval) until success / failed /
   node deadline (~250s). On success: inject filename-derived `metadata.title` if absent, set
   `raw_mcp_output` + `_track_id` (slug of filename).
5. Gateway → Musician → Analyst → Critic → Output (unchanged).
6. Worker: write `result_payload` to Supabase (`completed`); delete the temp file in `finally`.
7. Browser polls `GET /jobs/{id}` → `completed` → render.

### Demo path (step by step)
1. Browser: user selects a demo track + **Analyze** → `POST /demo {track_id}`.
2. `api.py /demo`: 404 if `track_id` not in the 3 demos; insert job; schedule
   `_run_job(job_id, demo_track_id=track_id)` (with `stress_test` from the track registry);
   return `{job_id}`.
3. Worker invokes graph with `{demo_track_id, audio_path: None, job_id, stress_test}`.
4. `mcp_node` (demo branch): load `cache/{track_id}.json`, set `raw_mcp_output` + `_track_id`.
   No network call.
5. Rest unchanged.

## Components

### `agents/mcp.py` (new — replaces `researcher.py` + `mcp_mock.py`)
Single `mcp_node(state)`:
- **demo branch** (`state["demo_track_id"]`): read `cache/{track_id}.json` → `raw_mcp_output`.
- **upload branch** (`state["audio_path"]`): `requests`-based POST/GET to Modal (matches the
  contract example; streams the file via `data=open(path,"rb")`), bounded poll loop with a
  deadline, defensive status handling per the OPEN ITEM above.
- On any failure sets `error` (+ routes to output via existing logic). Modal base URL from
  `MODAL_MCP_URL`; transient connection/5xx errors get ~2 `tenacity` retries.

### `agents/graph.py`
- Entry point `researcher` → **`mcp`**. Edges: `mcp → gateway → musician → analyst → critic →
  (conditional loop/END)`.
- `GraphState`: **remove** `user_input`, `youtube_url`, `researcher_metadata`; **add**
  `audio_path: str | None`, `audio_filename: str | None`, `demo_track_id: str | None`. Keep
  `job_id`, `_track_id`, `stress_test`.

### `api.py`
- `POST /analyze` — `multipart/form-data` `file`; validate + stream to temp; → `{job_id}`.
- `POST /demo` — JSON `{track_id}`; 404 if unknown; → `{job_id}`.
- `GET /jobs/{id}` — unchanged. `GET /tracks` — returns the **3** demos.
- Worker timeout **180s → 300s**. Temp upload deleted in `finally`.
- `_build_result_payload`: drop `youtube_url` and `researcher_reasoning`; `title`/`artist` from
  signature metadata (Modal's, or filename-derived title for uploads, artist `"—"`).
- `stress_test`: for `/demo`, taken from the track registry (HUMBLE = true); for `/analyze`,
  always false.

### Frontend (`frontend/src/`)
- `App.jsx`: **remove the YouTube search bar**. Input column = **"Upload your track"**
  (`FileUpload`, primary) + **"Or try a demo"** (`TrackSelector`, 3 tracks). `FileUpload` lifts
  the selected `File` to `App` via its existing `onFileChange`. **Analyze** posts multipart for an
  upload or `POST /demo` for a selected demo; enabled when either is set.
- `SignalSummary`: remove the YouTube link; tolerate a missing artist.
- Remove any `researcher_reasoning` display (e.g. in `ConfidencePanel`).
- Loader copy: "up to a minute" → "up to ~90 seconds". Keep timer-based stage captions.

## Removed

`agents/researcher.py`, `agents/mcp_mock.py`, `tests/test_researcher.py`, `yt-dlp` from
`requirements.txt`, and all `youtube_url` / `researcher_*` references across state, API, frontend,
and CLAUDE.md.

## Error handling

| Failure | Result |
|---|---|
| Bad file type / too big | `415` / `413` at `/analyze`, nothing queued |
| Modal unreachable / 5xx | retry ×2 → `mcp_node` sets `error` → job `failed` (clear message) |
| Modal job `failed` / poll deadline | job `failed` with Modal's reason |
| Backend worker > 300s | job `failed` "Analysis timed out" |
| Unknown demo `track_id` | `404` at `/demo` |
| Temp file | always deleted in worker `finally` |

## Testing

- Keep `test_gateway`, `test_analyst_rules`, `test_critic`, `test_output`.
- Replace `test_researcher` → **`test_mcp`**: demo branch loads a cache file; upload branch
  posts+polls against a **mocked** Modal HTTP (`responses`/monkeypatch) and asserts `raw_mcp_output`.
- Keep/adapt `test_mcp_contract`: Modal's poll payload validates against `SignalSignature`.
- Add API tests for `/analyze` (multipart) and `/demo` with the graph mocked.

## Config & docs

- `.env`: add `MODAL_MCP_URL` (prod base, e.g.
  `https://ripun-j-kashyap--audio-sonic-mcp-mcp-server.modal.run`); add an auth token var only if
  Modal requires one.
- `requirements.txt`: **−** `yt-dlp`; ensure `requests` is a direct dependency (used by `mcp_node`).
- **CLAUDE.md**: update flow, agents, API contract, GraphState, schemas notes, and "What Claude
  Should Never Do" to reflect the upload pipeline (Researcher/YouTube removed).

## Open items (confirm with Modal agent)
1. In-progress poll response shape (handled defensively until confirmed).
2. Auth on `/upload` and `/jobs` (assumed open).
3. Whether Modal's poll payload includes track `metadata` (title/artist) or only audio metrics.
