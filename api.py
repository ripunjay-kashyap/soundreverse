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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
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
    track_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/tracks")
def get_tracks():
    return TRACKS


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    valid_ids = {t["track_id"] for t in TRACKS}
    if req.track_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Track '{req.track_id}' not found in cache.")

    state = run_graph(req.track_id)

    if state.get("error"):
        raise HTTPException(status_code=500, detail=state["error"])

    sig      = state["signal_signature"]
    settings = state["producer_settings"]
    meta     = sig.metadata if sig else {}
    track_id = req.track_id

    return {
        "track": {
            "title":  meta.get("title", track_id),
            "artist": meta.get("artist", ""),
            "lufs":   sig.master.lufs   if sig else None,
            "bpm":    sig.rhythm.bpm    if sig else None,
            "key":    sig.rhythm.key    if sig else None,
        },
        "pipeline": {
            "confidence":        state["confidence"],
            "iteration_count":   state["iteration_count"],
            "max_iterations":    3,
            "critic_rounds":     state.get("critic_rounds", []),
            "validation_checks": state.get("validation_checks", []),
        },
        "settings": settings.model_dump() if settings else None,
        "trace_url": state.get("trace_url"),
        "outputs": {
            "pdf_url":      f"/outputs/{track_id}_blueprint.pdf",
            "json_url":     f"/outputs/{track_id}_preset.json",
            "metadata_url": f"/outputs/{track_id}_metadata.json",
        },
    }
