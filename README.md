# SoundReverse

**A LangGraph multi-agent system that reverse-engineers mastering decisions from a track's sonic fingerprint — producing EQ settings, compression parameters, and agent reasoning as a downloadable Producer Session Pack.**

---

## Dashboard

![SoundReverse Dashboard](screenshots/ui_dashboard_humble.png)

*HUMBLE. by Kendrick Lamar — 2-iteration run. Critic rejects iteration 1 (kick frequency mismatch), Analyst self-corrects, Critic approves at 100% confidence.*

---

## How It Works

### Signal Extraction — [custom MCP server](https://github.com/ripunjkashyap-a11y/Audio_stem_splt) (offline)

A custom MCP server built with **HTDemucs 4-stem**, **FFmpeg**, and **Librosa** separates a track into stems and extracts a `SignalSignature` — per-stem LUFS, dynamic range, spectral tilt, kick fundamental Hz, stereo correlation, BPM, key, and more.

Stem separation on CPU takes **15–20 minutes per track**. The 5 demo tracks ship with pre-computed signatures so the agentic pipeline runs on demand in seconds.

### Agentic Orchestration — LangGraph (on demand)

```
  SignalSignature JSON
          │
          ▼
   ┌─────────┐     ┌──────────┐     ┌────────┐
   │ Gateway │────▶│ Analyst  │────▶│ Critic │
   └─────────┘     └──────────┘     └────┬───┘
    validates        rules.yaml +         │ confidence < 0.8?
    schema           Gemini reasons       │ (max 3 iterations)
                         ▲               │
                         └───────────────┘
                                │ approved
                                ▼
                           Output Node
                     PDF + JSON preset + LangSmith trace URL
```

| Agent | Role | LLM |
|-------|------|-----|
| **Gateway** | Loads SignalSignature JSON, validates via Pydantic | No |
| **Analyst** | Evaluates `rules.yaml` deterministically, calls Gemini to write reason strings | Yes — structured tool call |
| **Critic** | Runs 4 physical-impossibility checks, calls Gemini to write critique + correction hints | Yes — structured tool call |

**Why two LLM agents?** The Analyst writes justifications for settings; the Critic reviews them and writes targeted correction hints that feed back into the Analyst's next prompt. The back-and-forth is visible in the LangSmith trace waterfall.

---

## LangSmith Trace

Every run produces a **public, shareable trace** — no login required.

![LangSmith Waterfall](screenshots/langsmith_trace_waterfall.png)

*2-iteration HUMBLE. run: gateway → analyst (LLM) → critic rejects (LLM) → analyst (LLM) → critic approves (LLM). 4 LLM calls, ~11s total.*

Live trace: [smith.langchain.com/public/58461f05-d106-47c2-93a4-bbf8460f4c2a/r](https://smith.langchain.com/public/58461f05-d106-47c2-93a4-bbf8460f4c2a/r)

---

## Producer Settings Output

![Producer Settings](screenshots/ui_producer_settings.png)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Signal extraction | HTDemucs 4-stem, FFmpeg, Librosa (custom MCP server) |
| Agent orchestration | LangGraph `StateGraph` |
| LLM | Gemini via `langchain-google-genai` — structured tool calling |
| Schema validation | Pydantic v2 |
| Rules engine | PyYAML — deterministic EQ/compression mapping |
| Observability | LangSmith — public trace URLs via `client.share_run()` |
| API | FastAPI + Uvicorn |
| Frontend | React + Vite + Tailwind CSS |
| PDF output | fpdf2 |

---

## Key Design Decisions

**Rules own the numbers, LLM owns the words.** All EQ frequencies, compression ratios, and gain values come from `rules.yaml` evaluated in Python. The LLM only writes the reason strings. This prevents hallucinated settings while keeping the output human-readable.

**Critic is deterministic on pass/fail, generative on narrative.** The 4 validation checks (over-compression, bright boost contradiction, loudness ceiling, kick frequency mismatch) are pure Python `if/else`. The LLM writes the critique and correction hints — making feedback actionable without letting the model decide what's physically valid.

**Output node runs outside the graph.** The LangSmith trace URL is only available after `app.invoke()` completes. The output generator runs post-invocation so the PDF and JSON embed the real trace URL.

---

## Project Structure

```
soundreverse/
├── agents/
│   ├── gateway.py          # Loads + validates SignalSignature JSON
│   ├── analyst.py          # Rules eval + Gemini reason writing
│   ├── critic.py           # Deterministic checks + Gemini critique
│   └── graph.py            # LangGraph StateGraph, run() entry point
├── schemas/
│   ├── signal_signature.py # Pydantic model — matches cache JSON exactly
│   ├── track_request.py
│   └── producer_settings.py
├── rules/
│   └── rules.yaml          # EQ/compression mapping rules
├── cache/                  # 5 pre-computed SignalSignature JSON files
├── output/
│   └── generator.py        # PDF blueprint + JSON preset writer
├── frontend/               # React + Vite dashboard
├── api.py                  # FastAPI server
└── tests/
```

---

## Setup

```bash
# 1. Clone and install
git clone https://github.com/ripunjkashyap-a11y/soundreverse.git
cd soundreverse
python -m venv venv && venv/Scripts/activate  # Windows
pip install -r requirements.txt

# 2. Environment variables
cp .env.example .env
# Fill in: GOOGLE_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGCHAIN_TRACING_V2=true

# 3. Run backend
uvicorn api:app --reload --port 8001

# 4. Run frontend (separate terminal)
cd frontend && npm install && npm run dev

# 5. Open http://localhost:5173
```

**CLI:**
```bash
python agents/graph.py --track humble_kendrick
```

**Tests:**
```bash
pytest tests/ -v
```

---

## Cached Tracks

| Track | Artist | |
|-------|--------|-|
| Billie Jean | Michael Jackson | |
| One More Time | Daft Punk | |
| Clocks | Coldplay | |
| HUMBLE. | Kendrick Lamar | ⚡ triggers 2-iteration critic loop |
| Blinding Lights | The Weeknd | |

⚡ HUMBLE. deliberately overshoots kick frequency on iteration 1 to demonstrate the Analyst–Critic rejection and self-correction cycle.
