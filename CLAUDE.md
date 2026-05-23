# SoundReverse — CLAUDE.md

## What This Project Is

A LangGraph multi-agent system that takes a **song query** (e.g. "Humble by Kendrick Lamar") and outputs a Producer Session Pack (EQ settings, compression parameters, plain-language musician notes, agent reasoning trace). A Researcher agent resolves the query to an official YouTube URL, an MCP step produces the track's `SignalSignature`, a Musician agent derives plain-language notes from it, and the Gateway → Analyst → Critic loop turns that into producer settings.

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
│   ├── researcher.py          ← yt-dlp search + Gemini → official YouTube URL, slug, metadata (+ _clean_youtube_url)
│   ├── mcp_mock.py            ← MOCK MCP: matches song → cache file, emits raw_mcp_output (real Modal MCP replaces this)
│   ├── gateway.py             ← validates raw_mcp_output (from state) against SignalSignature → TrackRequest
│   ├── musician.py            ← derives plain-language MusicianNotes (tuning targets + tonal tags) from the signature
│   ├── analyst.py             ← applies rules.yaml in pure Python; LLM only writes the reason strings → ProducerSettings
│   ├── critic.py              ← validates settings, loops max 3x
│   └── graph.py               ← LangGraph orchestration (researcher→mcp_mock→gateway→musician→analyst→critic)
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
├── api.py                     ← FastAPI async job queue (Supabase-backed): POST /analyze → job_id, GET /jobs/{id}; + orphan reaper & output sweeper
├── .mcp.json                  ← Supabase MCP server (Claude Code tooling — NOT app runtime)
├── plans/                     ← design notes (researcher_agent_plan.md)
├── BACKEND_IMPROVEMENT_PLAN.md ← production-readiness plan before real-MCP integration
├── tests/                     ← pytest: analyst_rules, critic, gateway, output, researcher, mcp_contract
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
├── .env                       ← GOOGLE_API_KEY, LANGSMITH_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY
├── render.yaml                 ← Render deploy config (backend)
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Orchestration:** LangGraph (Python)
- **LLM:** `gemini-3.1-flash-lite-preview` via `langchain-google-genai` — use this exact model string everywhere (defined as `MODEL` in analyst.py, critic.py, researcher.py, musician.py; also hardcoded in generator.py metadata)
- **Song search:** `yt-dlp` (`ytsearch3`) in the Researcher agent
- **Audio analysis:** external MCP server — **mock** today (`agents/mcp_mock.py`), **real server hosted on Modal** being integrated
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
Returns `{ track_id, label, stress_test }` for the 5 demo tracks (used by the frontend's suggestions).

### GET /outputs/{filename}
Serves generated files as static downloads, prefixed by `job_id` (e.g. `{job_id}_blueprint.pdf`). **Note:** these live on local disk and, in production (`ENV=production`/`PRODUCTION=true`), a background sweeper deletes files older than 1h every 15 min; they don't survive restarts — planned move to Supabase Storage (see `BACKEND_IMPROVEMENT_PLAN.md` §2A). On startup an **orphan reaper** marks any `pending`/`processing` job older than 10 min as `failed`.

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
Researcher → MCP (mock) → Gateway → Musician → Analyst → Critic → OUTPUT
                                                   ↑_________↓
                                                (max 3 loops)
```

`output_node` runs **outside** the graph (called in `run()` after `app.invoke()`), so the real LangSmith trace URL is available before generating files.

### Researcher Agent (`agents/researcher.py`)

- Receives `state["user_input"]` (a free-text song query or a URL)
- Uses `yt-dlp` (`ytsearch3`) to find candidates, then `gemini-3.1-flash-lite-preview` (tool-call → `ResearcherResult`) to pick the **official** channel/Topic upload
- Returns `youtube_url`, `researcher_metadata` (title, artist, slug, reasoning) into state
- Generates a slugified `track_id` (e.g. `humble_kendrick_lamar`)
- `_clean_youtube_url()` strips radio/`list=RD…`/`start_radio` params that break yt-dlp and the MCP downloader — applied to both the raw input and the resolved URL

### MCP Step (`agents/mcp_mock.py` → real Modal server)

- **Mock (today):** substring-matches the researched title/artist/slug to one of 5 cache files (defaults to `billie_jean_mj`), loads it, and emits `raw_mcp_output` (a dict conforming to `SignalSignature`) + `_track_id` into state
- **Real (being integrated):** a Modal-hosted service that takes the clean `youtube_url`, performs actual audio analysis, and returns the **same** `raw_mcp_output` shape. The Gateway contract is the swap point — keep it stable.

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

- Built with LangGraph `StateGraph`; entry point is `researcher`
- `GraphState` includes: `user_input`, `youtube_url`, `researcher_metadata`, `raw_mcp_output`, `_track_id`, `track_request`, `signal_signature`, `musician_notes`, `producer_settings`, `iteration_count`, `confidence`, `critique`, `critique_history`, `critic_rounds`, `validation_checks`, `final`, `error`, `trace_url`, `stress_test`, `job_id`
- Edges: Researcher → MCP(mock) → Gateway → Musician → Analyst → Critic → (conditional: loop back to Analyst OR END; `output_node` then runs outside the graph)
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

React + Vite + Tailwind (Tailwind v4 via `@tailwindcss/vite`; design tokens live in `src/index.css`). Calls `POST /analyze` then polls `GET /jobs/{id}` every 3s. In dev, `vite.config.js` proxies `/analyze`, `/jobs`, `/tracks`, `/outputs` to `127.0.0.1:8001`. Components: `TrackSelector`, `FileUpload` (frontend-only audio dropzone — captures into local state; **no upload endpoint yet**, awaiting the real MCP), `AnalyzeButton`, `SignalSummary`, `MusicianNotes`, `ConfidencePanel`, `CriticTimeline`, `ProducerSettings`, `OutputDownloads`. (The old Gradio `ui/app.py` has been replaced by this React app.)

---

## What Claude Should Never Do

- Run audio libraries (Demucs/Librosa/Essentia) **in this repo** — audio analysis belongs in the external MCP server (mock today, Modal-hosted real server being integrated)
- Use Redis
- Parse LLM free text to extract ProducerSettings — use structured output / tool calls
- Let the Analyst LLM pick settings or change numbers — rules are applied in pure Python (`_apply_rules`); the LLM only writes `reason` strings
- Allow iteration_count to exceed 3 under any circumstance
- Use any model other than `gemini-3.1-flash-lite-preview`
- Change the Gateway's `raw_mcp_output` → `SignalSignature` contract without updating the MCP contract (it is the real-MCP swap point)

---

## Further Reading

For more detail on specific parts of the system, read these files before working on them:

- `plans/researcher_agent_plan.md` — Researcher + Mock MCP design notes
- `BACKEND_IMPROVEMENT_PLAN.md` — production-readiness fixes required before real-MCP integration
