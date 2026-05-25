# SoundReverse — CLAUDE.md

> ## ⏳ Active Work — File-Upload Pivot (READ FIRST)
> **Branch:** `feature/file-upload-pivot`. Replacing YouTube ingestion with local mp3/wav upload → Modal MCP (+ 3 cached demo tracks). Full resume detail: `docs/superpowers/plans/2026-05-23-file-upload-pivot.md` → "Progress — RESUME HERE" and "Modal MCP — ANSWERED + SCHEMA BLOCKER".
>
> - **Done & committed:** Tasks 1–3 — deps (yt-dlp→requests); `agents/mcp.py` (demo + Modal client) + tests; graph rewired to `mcp` entry; `researcher.py`/`mcp_mock.py`/`test_researcher.py` deleted.
> - **Done, NOT committed (in working tree):** Task 4 — `api.py` (multipart `/analyze`, `/demo`, 300s worker, 3 demos) + `requirements.txt` (`python-multipart`); this CLAUDE.md update. Commit msgs are in the plan's RESUME HERE.
> - **⛔ Blocked on Modal:** Modal's payload is missing `stems` and uses a different shape (`header`/`sonic_signature`). The Modal agent is sending a reshaped, `SignalSignature`-shaped payload **with stems** — the user is bringing that answer into the next session.
> - **▶ DO FIRST next session:** wire the Modal agent's answer into `agents/mcp.py` — fix the poll logic (processing = `status` `queued`/`running`; done/fail via `header.status`), add an adapter if Modal keeps its native shape, bump timeouts (poll 250→~540, worker 300→~560), and validate a real sample against `tests/test_mcp_contract.py`. **Then:** commit Task 4 + docs → Task 5 (api tests) → Task 6 (frontend wiring) → Task 7 (`.env MODAL_MCP_URL`) → Task 8 (e2e). Demo path works today; only the upload path is blocked.

## What This Project Is

A LangGraph multi-agent system that takes an **uploaded audio file** (mp3/wav) — or one of 3 cached **demo tracks** — and outputs a Producer Session Pack (EQ settings, compression parameters, plain-language musician notes, agent reasoning trace). The MCP step produces the track's `SignalSignature`, a Musician agent derives plain-language notes from it, and the Gateway → Analyst → Critic loop turns that into producer settings.

**Audio analysis runs in an external MCP server, not in this process.** For uploads, the `mcp_node` streams the file to a **real Modal-hosted MCP** (`POST /upload`, then polls `/jobs/{id}`) which runs the Demucs/CLAP analysis and returns the `SignalSignature`. For demo tracks it loads a pre-computed `SignalSignature` JSON from `cache/` (no network). **The YouTube/yt-dlp ingestion was removed** — datacenter IPs get bot-blocked after deploy (see `docs/superpowers/specs/2026-05-23-file-upload-pivot-design.md`).

**Core rules:** No audio libraries in this repo (Demucs/Librosa/Essentia run inside the MCP server, never here). No Redis. Agents + LangGraph orchestration only.

---

## Project Structure

```
soundreverse/
├── CLAUDE.md                  ← you are here
├── cache/
│   ├── billie_jean_mj.json
│   ├── one_more_time_daft_punk.json
│   ├── clocks_coldplay.json
│   ├── humble_kendrick.json
│   └── blinding_lights_weeknd.json
├── agents/
│   ├── mcp.py                 ← entry node: demo → load cache/{id}.json; upload → POST file to Modal /upload + poll /jobs/{id}
│   ├── gateway.py             ← validates raw_mcp_output (from state) against SignalSignature → TrackRequest
│   ├── musician.py            ← derives plain-language MusicianNotes (tuning targets + tonal tags) from the signature
│   ├── analyst.py             ← applies rules.yaml in pure Python; LLM only writes the reason strings → ProducerSettings
│   ├── critic.py              ← validates settings, loops max 3x
│   └── graph.py               ← LangGraph orchestration (mcp→gateway→musician→analyst→critic)
├── schemas/
│   ├── signal_signature.py    ← Pydantic model for cache JSON
│   ├── track_request.py       ← Pydantic model for gateway output
│   ├── producer_settings.py   ← Pydantic model for analyst output
│   └── musician_notes.py      ← Pydantic model for musician output (MusicianNotes, TuningTarget)
├── rules/
│   └── rules.yaml             ← deterministic mapping rules the Analyst evaluates in pure Python
├── output/
│   └── generator.py           ← builds 2-page PDF + JSON preset + metadata; filenames prefixed by job_id (or track_id on CLI)
├── utils/
│   └── supabase_client.py     ← lazy-singleton get_supabase() shared by api.py
├── api.py                     ← FastAPI async job queue (Supabase-backed): POST /analyze (file upload), POST /demo, GET /jobs/{id}; + orphan reaper & output sweeper
├── .mcp.json                  ← Supabase MCP server (Claude Code tooling — NOT app runtime)
├── plans/                     ← design notes (researcher_agent_plan.md)
├── docs/superpowers/          ← specs/ and plans/ (file-upload pivot spec + implementation plan)
├── BACKEND_IMPROVEMENT_PLAN.md ← production-readiness plan before real-MCP integration
├── tests/                     ← pytest: analyst_rules, critic, gateway, output, mcp, mcp_contract, api
├── frontend/                  ← React + Vite + Tailwind UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── TrackSelector.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   ├── AnalyzeButton.jsx
│   │   │   ├── SignalSummary.jsx
│   │   │   ├── MusicianNotes.jsx
│   │   │   ├── ConfidencePanel.jsx
│   │   │   ├── CriticTimeline.jsx
│   │   │   ├── ProducerSettings.jsx
│   │   │   └── OutputDownloads.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .env                       ← GOOGLE_API_KEY, LANGSMITH_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, MODAL_MCP_URL
├── render.yaml                 ← Render deploy config (backend)
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Orchestration:** LangGraph (Python)
- **LLM:** `gemini-3.1-flash-lite-preview` via `langchain-google-genai` — use this exact model string everywhere (defined as `MODEL` in analyst.py, critic.py, musician.py; also hardcoded in generator.py metadata)
- **Audio in:** local **mp3/wav upload** → Modal MCP (`POST /upload` binary, poll `/jobs/{id}`) via `requests` in `agents/mcp.py`; demo tracks load cached `SignalSignature` JSON
- **Audio analysis:** external **Modal-hosted MCP** (real Demucs/CLAP); no audio libraries in this repo
- **Schemas:** Pydantic v2
- **Rules engine:** PyYAML
- **PDF output:** fpdf2
- **API:** FastAPI + uvicorn (`api.py` at project root) — async job queue
- **Job state:** Supabase (`jobs` table) via the `supabase` Python client (shared lazy singleton in `utils/supabase_client.py`)
- **Frontend:** React + Vite + Tailwind CSS (no component library) in `frontend/`
- **Tracing:** LangSmith (required — every run must produce a trace)
- **Cache:** flat JSON files in `/cache` — no Redis

---

## API Contract

The API is **asynchronous**: `/analyze` and `/demo` enqueue a job and return immediately; the client **polls** `/jobs/{id}`. This is required because the analysis pipeline (Modal upload + analysis + multiple Gemini calls, ~70–95s, longer on a cold Modal container) far exceeds an HTTP request window.

### POST /analyze  → `202 Accepted`  (file upload)
`multipart/form-data` with a `file` field (mp3/wav, ≤50 MB). Streams the file to a temp path, inserts a Supabase `jobs` row (`status: "pending"`), runs the graph in the background.
```json
// Response
{ "job_id": "uuid" }
```
Errors: `415` (not mp3/wav), `413` (>50 MB).

### POST /demo  → `202 Accepted`  (cached track, no Modal)
```json
// Request
{ "track_id": "humble_kendrick" }
// Response
{ "job_id": "uuid" }
```
`404` if `track_id` is not one of the 3 demos.

### GET /jobs/{job_id}
```json
// completed
{ "job_id": "uuid", "status": "completed", "result": {
    "track":    { "title": "...", "artist": "...", "lufs": -6.8, "bpm": 150.0, "key": "Eb Minor" },
    "pipeline": { "confidence": 1.0, "iteration_count": 2, "max_iterations": 3,
                  "critic_rounds": [...], "validation_checks": [...] },
    "settings":  { "eq": [...], "compression": {...}, "compression_skip_reason": "...",
                   "master_gain_db": 0, "master_gain_reason": "..." },
    "musician":  { "tuning_targets": [...], "tuning_tip": "...", "tonal_tags": [...], "tonal_character": "..." },
    "trace_url": "https://smith.langchain.com/...",
    "outputs":   { "pdf_url": "...", "json_url": "...", "metadata_url": "..." } } }
// outputs filenames are prefixed by job_id, e.g. /outputs/{job_id}_blueprint.pdf
// pending / processing
{ "job_id": "uuid", "status": "processing" }
// failed
{ "job_id": "uuid", "status": "failed", "error": "..." }
```

### GET /tracks
Returns `{ track_id, label, stress_test }` for the 3 demo tracks (used by the frontend's "Or try a demo" list).

### GET /outputs/{filename}
Serves generated files as static downloads, prefixed by `job_id` (e.g. `{job_id}_blueprint.pdf`). **Note:** these live on local disk and, in production (`ENV=production`/`PRODUCTION=true`), a background sweeper deletes files older than 1h every 15 min; they don't survive restarts — planned move to Supabase Storage (see `BACKEND_IMPROVEMENT_PLAN.md` §2A). On startup an **orphan reaper** marks any `pending`/`processing` job older than 10 min as `failed`.

---

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full agent graph (CLI)
python -m agents.graph --demo humble_kendrick        # cached demo track (no Modal)
python -m agents.graph --file path/to/song.mp3       # local upload → Modal MCP (needs MODAL_MCP_URL)

# Launch FastAPI backend (use venv python directly on Windows)
venv/Scripts/python -m uvicorn api:app --reload --port 8001

# Launch React frontend (from frontend/ dir)
cd frontend && npm run dev

# Validate all cache JSON files against Pydantic schema
python schemas/signal_signature.py --validate-all

# Run tests
pytest tests/ -v
```

---

## Agent Architecture

### The Flow

```
Upload / Demo → MCP → Gateway → Musician → Analyst → Critic → OUTPUT
                                              ↑_________↓
                                           (max 3 loops)
```

`output_node` runs **outside** the graph (called in `run()` after `app.invoke()`), so the real LangSmith trace URL is available before generating files.

### MCP Node (`agents/mcp.py`) — entry point

- **Demo branch** (`state["demo_track_id"]`): loads `cache/{track_id}.json` → `raw_mcp_output` + `_track_id`. No network.
- **Upload branch** (`state["audio_path"]`): streams the file to `${MODAL_MCP_URL}/upload` (raw bytes, `X-Filename` header) → gets a Modal job id → polls `${MODAL_MCP_URL}/jobs/{id}` (~3s interval, ~250s deadline) until the `SignalSignature` JSON is ready. The uploaded **filename (minus extension) becomes the display title**; `track_id` is its slug.
- Modal status vocab is `"success"`; the poll is treated as done when the payload carries the signature keys (`master`/`stems`/`rhythm`). Transient connection/5xx errors get ~2 `tenacity` retries; any failure sets `error` + `final`.
- The **Gateway contract (`raw_mcp_output` → `SignalSignature`) is the swap point** — both branches must produce that shape.

### Gateway Agent (`agents/gateway.py`)

- Reads `raw_mcp_output` from `GraphState` (no longer reads files directly)
- Validates it with `SignalSignature.model_validate(raw_data)`
- Returns a `TrackRequest`; on validation failure sets `error` + `final` and routes to output

**No LLM call in the Gateway. It is pure Python.**

### Musician Agent (`agents/musician.py`)

- Runs **between Gateway and Analyst**; reads `signal_signature` and writes `musician_notes` (a `MusicianNotes`) into state
- **Deterministic facts (no LLM):** per-stem fundamentals → `TuningTarget`s (Hz + nearest note via `_hz_to_note`), plus plain-language `tonal_tags` derived from master energy ratios / spectral tilt / stereo metrics
- **LLM phrasing (grounded):** a tool-call (`_NotesDraft`) writes a friendly `tuning_tip` + `tonal_character` using only the given facts — it must not invent numbers
- **Supplementary & resilient:** if the LLM call fails it degrades to deterministic fallback text and **never fails the run** (if there's no signature it passes state through untouched)
- Aimed at the non-technical-musician audience — this becomes page 1 of the PDF and the `MusicianNotes` card in the UI

### Analyst Agent (`agents/analyst.py`)

- Receives `SignalSignature` + the current `critique` + `iteration_count`
- Loads `rules/rules.yaml` and evaluates every rule in **pure Python** (`_apply_rules`) — this is what decides the EQ bands, compression, and master gain. **The LLM never picks settings or numbers.**
- The LLM call (`_refine_reasons`, tool-call → `ReasonBundle`) only **rewrites the human-readable `reason` strings**, grounded in the deterministic draft plus any prior critique — it must not invent settings or change values
- Builds a valid `ProducerSettings` (Pydantic) from the draft + refined reasons; each `reason` references the actual metric value (e.g. `"spectral_tilt=0.74"`)
- **Stress test** lives here: when `stress_test` is set and `iteration_count == 0`, the kick-fundamental EQ freq is deliberately overshot by +30 Hz to exercise the Analyst→Critic rejection loop
- On Gemini failure returns a clear `error` (5xx → retryable message; 4xx → key/quota message) instead of crashing

### Critic Agent (`agents/critic.py`)

- Receives `SignalSignature` + `ProducerSettings` + `iteration_count`
- Cross-validates settings against raw metrics
- Produces a `confidence` score (float 0.0–1.0)
- If `confidence >= 0.75` OR `iteration_count >= 3`: sign off and return final output
- If `confidence < 0.75` AND `iteration_count < 3`: return rejection with specific reason, increment counter, send back to Analyst
- The rejection reason must quote the exact metric that caused the mismatch
- Emits `critic_rounds` (per-iteration log) and final-round `validation_checks` into state for the UI and the metadata JSON

### Graph (`agents/graph.py`)

- Built with LangGraph `StateGraph`; entry point is `mcp`
- `GraphState` includes: `audio_path`, `audio_filename`, `demo_track_id`, `raw_mcp_output`, `_track_id`, `track_request`, `signal_signature`, `musician_notes`, `producer_settings`, `iteration_count`, `confidence`, `critique`, `critique_history`, `critic_rounds`, `validation_checks`, `final`, `error`, `trace_url`, `stress_test`, `job_id`
- Edges: MCP → Gateway → Musician → Analyst → Critic → (conditional: loop back to Analyst OR END; `output_node` then runs outside the graph)
- `run(audio_path=None, audio_filename=None, demo_track_id=None, stress_test=False, job_id=None)`; CLI: `--demo <id>` or `--file <path>`
- LangSmith tracing must be enabled via environment variable — every run produces a shareable URL

---

## Schemas

### SignalSignature (matches cache JSON exactly)

```python
class StemMetrics(BaseModel):
    lufs: float
    peak_db: float
    dynamic_range_db: float
    spectral_tilt: float
    stereo_correlation: float
    kick_fundamental_hz: float | None = None   # drums stem only
    snare_fundamental_hz: float | None = None  # drums stem only
    transient_sharpness: float | None = None   # drums stem only
    fundamental_hz: float | None = None        # bass + vocals stems
    presence_peak_hz: float | None = None      # vocals stem only

class MasterMetrics(BaseModel):
    lufs: float
    peak_db: float
    true_peak_dbtp: float
    dynamic_range_db: float
    spectral_tilt: float
    stereo_correlation: float
    stereo_width: float
    low_energy_ratio: float
    mid_energy_ratio: float
    high_energy_ratio: float

class RhythmMetrics(BaseModel):
    bpm: float
    bpm_confidence: float
    key: str
    key_confidence: float
    time_signature: str

class SignalSignature(BaseModel):
    track_id: str
    metadata: dict
    stems: dict[str, StemMetrics]
    master: MasterMetrics
    rhythm: RhythmMetrics
```

### ProducerSettings (Analyst output)

```python
class EQBand(BaseModel):
    band: str
    freq: int
    gain_db: float
    q: float | None = None
    reason: str              # must reference actual metric

class Compression(BaseModel):
    ratio: str
    attack_ms: int
    release_ms: int
    reason: str

class ProducerSettings(BaseModel):
    eq: list[EQBand]
    compression: Compression | None
    compression_skip_reason: str | None = None   # set instead of compression.reason when compression is skipped
    master_gain_db: float
    master_gain_reason: str | None = None
    confidence: float | None = None
    iteration_count: int = 0
```

### MusicianNotes (Musician output)

```python
class TuningTarget(BaseModel):
    element: str       # e.g. "Kick", "Bass", "Vocal presence"
    hz: float
    note: str          # nearest musical note, e.g. "B1"

class MusicianNotes(BaseModel):
    tuning_targets: list[TuningTarget] = []
    tuning_tip: str = ""          # plain-language line on how to use the targets (LLM, grounded)
    tonal_tags: list[str] = []    # e.g. ["Bass-forward", "Bright", "Mono-solid"] (deterministic)
    tonal_character: str = ""     # 1-2 sentence description (LLM, grounded)
```

---

## Rules File (`rules/rules.yaml`)

The Analyst **loads and evaluates these rules in pure Python** (`_apply_rules`) — the LLM never invents mappings; it only phrases the `reason` strings afterward.

```yaml
rules:
  - id: spectral_tilt_bright
    condition: "master.spectral_tilt > 0.7"
    action:
      eq_band: { band: "high_shelf", freq: 10000, gain_db: -2.5, q: null }
    reason_template: "spectral_tilt={value} — bright mix, high shelf cut"

  - id: spectral_tilt_dark
    condition: "master.spectral_tilt < 0.4"
    action:
      eq_band: { band: "high_shelf", freq: 8000, gain_db: +1.5, q: null }
    reason_template: "spectral_tilt={value} — dark mix, high shelf boost"

  - id: kick_fundamental_boost
    condition: "stems.drums.kick_fundamental_hz is not null"
    action:
      eq_band: { band: "low_peak", freq: "{kick_fundamental_hz}", gain_db: +2.0, q: 1.2 }
    reason_template: "kick fundamental at {value}Hz"

  - id: heavy_compression_skip
    condition: "master.dynamic_range_db < 5"
    action:
      compression: null
    reason_template: "DR={value}dB — already heavily compressed, skip bus compression"

  - id: moderate_compression
    condition: "master.dynamic_range_db >= 5 and master.dynamic_range_db <= 10"
    action:
      compression: { ratio: "4:1", attack_ms: 10, release_ms: 80 }
    reason_template: "DR={value}dB — moderate compression applied"

  - id: loud_master
    condition: "master.lufs > -10"
    action:
      master_gain_db: 0
    reason_template: "LUFS={value} — already at streaming loudness target"

  - id: quiet_master
    condition: "master.lufs < -14"
    action:
      master_gain_db: +3
    reason_template: "LUFS={value} — below streaming target, gain applied"
```

---

## Critic Validation Rules

These are the physical impossibility checks the Critic must enforce:

- If `compression.ratio` is not null AND `master.dynamic_range_db < 4` → flag as contradiction (over-compression)
- If any EQ `gain_db > 0` on high shelf AND `master.spectral_tilt > 0.75` → flag (boosting already bright mix)
- If `master_gain_db > 0` AND `master.lufs > -9` → flag (pushing an already loud master)
- If `kick_fundamental_hz` boost freq differs from `stems.drums.kick_fundamental_hz` by more than 20Hz → flag

---

## Output Generator (`output/generator.py`)

Runs **outside** the graph (in `run()` after `app.invoke()`), so the real LangSmith trace URL is captured first. Produces **three files per run**, all prefixed by `job_id` when present (else `track_id`):

**1. Blueprint PDF** — `{prefix}_blueprint.pdf` (via fpdf2, indigo/slate theme, 2 pages)
- Page 1 (at-a-glance, **musician-first**): hero + stat cards (BPM / Key / LUFS / DR) → Tonal Character + Tuning Targets (from `MusicianNotes`) → EQ Moves table → Bus Compression & Master Gain
- Page 2 (reference): Mix Signal Profile (measured metrics) → "Why These Settings" reason blocks per EQ band / compression / master gain → confidence pill
- The critic debate log is **not** in the PDF — it lives in the metadata JSON (`critic_rounds`)
- Footer with page number on every page; non-latin-1 chars are sanitized so Helvetica won't crash

**2. JSON Preset** — `{prefix}_preset.json`
- Raw `ProducerSettings` dict + `track_id`, `trace_url`, `confidence`, `iteration_count` at top level

**3. Metadata JSON** — `{prefix}_metadata.json`
- `run_id`, `timestamp`, `track_id`, per-stage `pipeline` info, `critic_rounds`, `trace_url`

---

## LangSmith Setup

```bash
# Required in .env
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=soundreverse-v1
LANGCHAIN_TRACING_V2=true
```

Every run must log to LangSmith. The trace URL must be captured after graph execution and included in all three output files. If LangSmith is not configured, the app should warn but not crash.

---

## Frontend (`frontend/`)

React + Vite + Tailwind (Tailwind v4 via `@tailwindcss/vite`; design tokens live in `src/index.css`). Input column is **upload-primary**: `FileUpload` (drag-drop mp3/wav) posts `multipart` to `POST /analyze`; `TrackSelector` lists the 3 demos and posts `POST /demo {track_id}`. Then polls `GET /jobs/{id}` every 3s. In dev, `vite.config.js` proxies `/analyze`, `/demo`, `/jobs`, `/tracks`, `/outputs` to `127.0.0.1:8001`. Components: `FileUpload`, `TrackSelector`, `AnalyzeButton`, `SignalSummary`, `MusicianNotes`, `ConfidencePanel`, `CriticTimeline`, `ProducerSettings`, `OutputDownloads`.

> **Status:** the frontend wiring (remove the old YouTube search bar, lift the uploaded `File` to `App`, post to `/analyze` vs `/demo`) is **Task 6 of the pivot plan — not yet implemented.** See `docs/superpowers/plans/2026-05-23-file-upload-pivot.md`.

---

## What Claude Should Never Do

- Run audio libraries (Demucs/Librosa/Essentia) **in this repo** — audio analysis belongs in the external Modal-hosted MCP
- **Reintroduce yt-dlp / any YouTube ingestion** — datacenter IPs are bot-blocked after deploy; input is local upload (or cached demo). See `docs/superpowers/specs/2026-05-23-file-upload-pivot-design.md`
- Use Redis
- Parse LLM free text to extract ProducerSettings — use structured output / tool calls
- Let the Analyst LLM pick settings or change numbers — rules are applied in pure Python (`_apply_rules`); the LLM only writes `reason` strings
- Allow iteration_count to exceed 3 under any circumstance
- Use any model other than `gemini-3.1-flash-lite-preview`
- Change the Gateway's `raw_mcp_output` → `SignalSignature` contract without updating the Modal MCP contract (it is the swap point both the demo and upload branches must satisfy)

---

## Further Reading

For more detail on specific parts of the system, read these files before working on them:

- `docs/superpowers/specs/2026-05-23-file-upload-pivot-design.md` — the file-upload pivot design (why YouTube was removed, Modal contract, error handling)
- `docs/superpowers/plans/2026-05-23-file-upload-pivot.md` — the implementation plan (task-by-task; current progress tracked there)
- `BACKEND_IMPROVEMENT_PLAN.md` — production-readiness fixes
- `plans/researcher_agent_plan.md` — **historical** (Researcher + Mock MCP; both removed in the pivot)
