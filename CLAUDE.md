# SoundReverse — CLAUDE.md

## What This Project Is

A LangGraph multi-agent system that takes a **song query** (e.g. "Humble by Kendrick Lamar") and outputs a Producer Session Pack (EQ settings, compression parameters, agent reasoning trace). A Researcher agent resolves the query to an official YouTube URL, an MCP step produces the track's `SignalSignature`, and the Gateway → Analyst → Critic loop turns that into producer settings.

**Audio analysis runs in an external MCP server, not in this process.** Today that step is a **mock** (`agents/mcp_mock.py`) that returns one of 5 pre-cached `SignalSignature` JSON files; a **real MCP server hosted on Modal** is being integrated to replace it (returns the same `SignalSignature` shape from real audio). See `BACKEND_IMPROVEMENT_PLAN.md` for the integration plan.

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
│   ├── researcher.py          ← yt-dlp search + Gemini → official YouTube URL, slug, metadata
│   ├── mcp_mock.py            ← MOCK MCP: matches song → cache file, emits raw_mcp_output (real Modal MCP replaces this)
│   ├── gateway.py             ← validates raw_mcp_output (from state) against SignalSignature → TrackRequest
│   ├── analyst.py             ← maps SignalSignature → ProducerSettings
│   ├── critic.py              ← validates settings, loops max 3x
│   └── graph.py               ← LangGraph orchestration (researcher→mcp_mock→gateway→analyst→critic)
├── schemas/
│   ├── signal_signature.py    ← Pydantic model for cache JSON
│   ├── track_request.py       ← Pydantic model for gateway output
│   └── producer_settings.py   ← Pydantic model for analyst output
├── rules/
│   └── rules.yaml             ← deterministic mapping rules for Analyst
├── output/
│   └── generator.py           ← builds PDF + JSON preset + metadata from final settings
├── api.py                     ← FastAPI async job queue (Supabase-backed): POST /analyze → job_id, GET /jobs/{id}
├── .mcp.json                  ← Supabase MCP server (Claude Code tooling — NOT app runtime)
├── plans/                     ← design notes (researcher_agent_plan.md)
├── BACKEND_IMPROVEMENT_PLAN.md ← production-readiness plan before real-MCP integration
├── tests/                     ← pytest: analyst_rules, critic, gateway, output (researcher/mcp_mock untested)
├── frontend/                  ← React + Vite + Tailwind UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── TrackSelector.jsx
│   │   │   ├── AnalyzeButton.jsx
│   │   │   ├── SignalSummary.jsx
│   │   │   ├── ConfidencePanel.jsx
│   │   │   ├── CriticTimeline.jsx
│   │   │   └── OutputDownloads.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .env                       ← GOOGLE_API_KEY, LANGSMITH_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY
├── render.yaml                 ← Render deploy config (backend)
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Orchestration:** LangGraph (Python)
- **LLM:** `gemini-3.1-flash-lite-preview` via `langchain-google-genai` — use this exact model string everywhere (defined as `MODEL` in analyst.py, critic.py, researcher.py; also hardcoded in generator.py metadata)
- **Song search:** `yt-dlp` (`ytsearch3`) in the Researcher agent
- **Audio analysis:** external MCP server — **mock** today (`agents/mcp_mock.py`), **real server hosted on Modal** being integrated
- **Schemas:** Pydantic v2
- **Rules engine:** PyYAML
- **PDF output:** fpdf2
- **API:** FastAPI + uvicorn (`api.py` at project root) — async job queue
- **Job state:** Supabase (`jobs` table) via the `supabase` Python client
- **Frontend:** React + Vite + Tailwind CSS (no component library) in `frontend/`
- **Tracing:** LangSmith (required — every run must produce a trace)
- **Cache:** flat JSON files in `/cache` — no Redis

---

## API Contract

The API is **asynchronous**: `/analyze` enqueues a job and returns immediately; the client **polls** `/jobs/{id}`. This is required because the analysis pipeline (yt-dlp + multiple Gemini calls + the Modal MCP at 20s–2min) far exceeds an HTTP request window.

### POST /analyze  → `202 Accepted`
```json
// Request
{ "user_input": "Humble by Kendrick Lamar" }

// Response
{ "job_id": "uuid" }
```
Inserts a row into the Supabase `jobs` table (`status: "pending"`) and runs the graph in the background (`status: pending → processing → completed | failed`).

### GET /jobs/{job_id}
```json
// completed
{ "job_id": "uuid", "status": "completed", "result": {
    "track":    { "title": "...", "artist": "...", "lufs": -6.8, "bpm": 150.0, "key": "Eb Minor", "youtube_url": "..." },
    "pipeline": { "confidence": 1.0, "iteration_count": 2, "max_iterations": 3,
                  "critic_rounds": [...], "validation_checks": [...], "researcher_reasoning": "..." },
    "settings":  { "eq": [...], "compression": {...}, "master_gain_db": 0 },
    "trace_url": "https://smith.langchain.com/...",
    "outputs":   { "pdf_url": "...", "json_url": "...", "metadata_url": "..." } } }
// pending / processing
{ "job_id": "uuid", "status": "processing" }
// failed
{ "job_id": "uuid", "status": "failed", "error": "..." }
```

### GET /tracks
Returns `{ track_id, label, stress_test }` for the 5 demo tracks (used by the frontend's suggestions).

### GET /outputs/{filename}
Serves generated files as static downloads. **Note:** these live on local disk today and do not survive restarts — planned move to Supabase Storage (see `BACKEND_IMPROVEMENT_PLAN.md` §2A).

---

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full agent graph (CLI) — --track is a free-text song query fed to the Researcher
python -m agents.graph --track "Humble by Kendrick Lamar"

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
Researcher → MCP (mock) → Gateway → Analyst → Critic → OUTPUT
                                        ↑_________↓
                                     (max 3 loops)
```

`output_node` runs **outside** the graph (called in `run()` after `app.invoke()`), so the real LangSmith trace URL is available before generating files.

### Researcher Agent (`agents/researcher.py`)

- Receives `state["user_input"]` (a free-text song query or a URL)
- Uses `yt-dlp` (`ytsearch3`) to find candidates, then `gemini-3.1-flash-lite-preview` (tool-call → `ResearcherResult`) to pick the **official** channel/Topic upload
- Returns `youtube_url`, `researcher_metadata` (title, artist, slug, reasoning) into state
- Generates a slugified `track_id` (e.g. `humble_kendrick_lamar`)
- **Planned:** `_clean_youtube_url()` to strip radio/`list=RD…`/`start_radio` params that break yt-dlp and the MCP downloader (see `BACKEND_IMPROVEMENT_PLAN.md` §3.1)

### MCP Step (`agents/mcp_mock.py` → real Modal server)

- **Mock (today):** substring-matches the researched title/artist/slug to one of 5 cache files (defaults to `billie_jean_mj`), loads it, and emits `raw_mcp_output` (a dict conforming to `SignalSignature`) + `_track_id` into state
- **Real (being integrated):** a Modal-hosted service that takes the clean `youtube_url`, performs actual audio analysis, and returns the **same** `raw_mcp_output` shape. The Gateway contract is the swap point — keep it stable.

### Gateway Agent (`agents/gateway.py`)

- Reads `raw_mcp_output` from `GraphState` (no longer reads files directly)
- Validates it with `SignalSignature.model_validate(raw_data)`
- Returns a `TrackRequest`; on validation failure sets `error` + `final` and routes to output

**No LLM call in the Gateway. It is pure Python.**

### Analyst Agent (`agents/analyst.py`)

- Receives `SignalSignature` JSON
- Loads `rules/rules.yaml` at runtime
- Sends both to `gemini-3.1-flash-lite-preview` with a structured prompt
- Must return a valid `ProducerSettings` object (Pydantic)
- Each setting must include a `reason` field referencing the actual metric value (e.g. `"spectral_tilt=0.74"`)
- Use structured output / tool use to enforce the schema — do not parse free text

### Critic Agent (`agents/critic.py`)

- Receives `SignalSignature` + `ProducerSettings` + `iteration_count`
- Cross-validates settings against raw metrics
- Produces a `confidence` score (float 0.0–1.0)
- If `confidence >= 0.75` OR `iteration_count >= 3`: sign off and return final output
- If `confidence < 0.75` AND `iteration_count < 3`: return rejection with specific reason, increment counter, send back to Analyst
- The rejection reason must quote the exact metric that caused the mismatch

### Graph (`agents/graph.py`)

- Built with LangGraph `StateGraph`; entry point is `researcher`
- `GraphState` includes: `user_input`, `youtube_url`, `researcher_metadata`, `raw_mcp_output`, `_track_id`, `track_request`, `signal_signature`, `producer_settings`, `iteration_count`, `confidence`, `critique`, `critique_history`, `critic_rounds`, `validation_checks`, `final`, `error`, `trace_url`, `stress_test`
- Edges: Researcher → MCP(mock) → Gateway → Analyst → Critic → (conditional: loop back to Analyst OR proceed to Output/END)
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
    master_gain_db: float
    confidence: float | None = None
    iteration_count: int = 0
```

---

## Rules File (`rules/rules.yaml`)

The Analyst must load and follow these rules. Do not let the LLM invent mappings.

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

Produces two files per run:

**1. Blueprint PDF** (via fpdf2)
- Page 1: Track metadata + EQ settings table + Compression settings
- Page 2: Agent reasoning — each setting with its `reason` field
- Page 3: Critic debate log — what was rejected, why, how many iterations
- Footer: LangSmith trace URL on every page

**2. JSON Preset** (`{track_id}_preset.json`)
- Raw `ProducerSettings` dict
- Include `trace_url`, `confidence`, `iteration_count` at top level

---

## LangSmith Setup

```bash
# Required in .env
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=soundreverse-v1
LANGCHAIN_TRACING_V2=true
```

Every run must log to LangSmith. The trace URL must be captured after graph execution and included in both output files. If LangSmith is not configured, the app should warn but not crash.

---

## Frontend (`frontend/`)

React + Vite + Tailwind. Calls `POST /analyze` then polls `GET /jobs/{id}`. Components: `TrackSelector`, `AnalyzeButton`, `SignalSummary`, `ConfidencePanel`, `CriticTimeline`, `ProducerSettings`, `OutputDownloads`. (The old Gradio `ui/app.py` has been replaced by this React app.)

---

## What Claude Should Never Do

- Run audio libraries (Demucs/Librosa/Essentia) **in this repo** — audio analysis belongs in the external MCP server (mock today, Modal-hosted real server being integrated)
- Use Redis
- Parse LLM free text to extract ProducerSettings — use structured output / tool calls
- Let the Analyst invent EQ settings not grounded in `rules.yaml`
- Allow iteration_count to exceed 3 under any circumstance
- Use any model other than `gemini-3.1-flash-lite-preview`
- Change the Gateway's `raw_mcp_output` → `SignalSignature` contract without updating the MCP contract (it is the real-MCP swap point)

---

## Agent Docs

For more detail on specific parts of the system, read these files before working on them:

- `agent_docs/graph_state.md` — full LangGraph state schema and edge logic
- `agent_docs/prompt_templates.md` — exact prompts for Analyst and Critic
- `agent_docs/output_format.md` — PDF layout specs and JSON preset schema
- `plans/researcher_agent_plan.md` — Researcher + Mock MCP design notes
- `BACKEND_IMPROVEMENT_PLAN.md` — production-readiness fixes required before real-MCP integration
