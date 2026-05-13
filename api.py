import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.graph import run as run_graph

app = FastAPI(title="SoundReverse API", version="1.0.0")

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(Path(__file__).parent / "output")))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# ── Track registry ────────────────────────────────────────────────────────────

TRACKS = [
    {"track_id": "billie_jean_mj",          "label": "Billie Jean — Michael Jackson",    "stress_test": False},
    {"track_id": "one_more_time_daft_punk",  "label": "One More Time — Daft Punk",        "stress_test": False},
    {"track_id": "clocks_coldplay",          "label": "Clocks — Coldplay",                "stress_test": False},
    {"track_id": "humble_kendrick",          "label": "HUMBLE. — Kendrick Lamar",         "stress_test": True},
    {"track_id": "blinding_lights_weeknd",   "label": "Blinding Lights — The Weeknd",     "stress_test": False},
]


# ── Request / Response models ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    user_input: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/tracks")
def get_tracks():
    return TRACKS


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    # Determine if this is a stress test (Humble by Kendrick Lamar is our demo for this)
    stress_test = "humble" in req.user_input.lower()

    # run_graph is synchronous (LangGraph + Gemini calls); offload to thread pool
    # so the FastAPI event loop stays free to handle other requests during the ~20s run
    state = await asyncio.to_thread(run_graph, req.user_input, stress_test)

    if state.get("error"):
        raise HTTPException(status_code=500, detail=state["error"])

    sig      = state["signal_signature"]
    settings = state["producer_settings"]
    meta     = sig.metadata if sig else {}
    researcher_meta = state.get("researcher_metadata", {})
    track_id = state.get("_track_id", "unknown")

    return {
        "track": {
            "title":  researcher_meta.get("title") or meta.get("title", track_id),
            "artist": researcher_meta.get("artist") or meta.get("artist", ""),
            "lufs":   sig.master.lufs   if sig else None,
            "bpm":    sig.rhythm.bpm    if sig else None,
            "key":    sig.rhythm.key    if sig else None,
            "youtube_url": state.get("youtube_url"),
        },
        "pipeline": {
            "confidence":        state["confidence"],
            "iteration_count":   state["iteration_count"],
            "max_iterations":    3,
            "critic_rounds":     state.get("critic_rounds", []),
            "validation_checks": state.get("validation_checks", []),
            "researcher_reasoning": researcher_meta.get("reasoning"),
        },
        "settings": settings.model_dump() if settings else None,
        "trace_url": state.get("trace_url"),
        "outputs": {
            "pdf_url":      f"/outputs/{track_id}_blueprint.pdf",
            "json_url":     f"/outputs/{track_id}_preset.json",
            "metadata_url": f"/outputs/{track_id}_metadata.json",
        },
    }
