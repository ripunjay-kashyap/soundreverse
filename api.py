import asyncio
import os
import sys
import uuid
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.graph import run as run_graph
from utils.supabase_client import get_supabase

# ── Lifespan & Background Tasks ──────────────────────────────────────────────

async def reap_orphan_jobs() -> None:
    """Startup check: Mark processing/pending jobs older than 10 minutes as failed."""
    try:
        sb = get_supabase()
        
        # Find all processing/pending jobs
        res = sb.table("jobs").select("id, status, updated_at, created_at").or_("status.eq.processing,status.eq.pending").execute()
        
        if res.data:
            reaped_count = 0
            for job in res.data:
                # Compare timestamp
                time_str = job.get("updated_at") or job.get("created_at")
                if time_str:
                    try:
                        # Parse ISO timestamp, normalizing Z to +00:00 for compatibility
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        if dt < datetime.now(timezone.utc) - timedelta(minutes=10):
                            sb.table("jobs").update({
                                "status": "failed",
                                "error_message": "Job orphaned (process terminated or timed out).",
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }).eq("id", job["id"]).execute()
                            reaped_count += 1
                    except Exception as parse_err:
                        print(f"[Orphan Reaper] Error parsing timestamp for job {job['id']}: {parse_err}")
            if reaped_count > 0:
                print(f"[Orphan Reaper] Successfully reaped {reaped_count} stuck/orphaned jobs.")
    except Exception as e:
        print(f"[Orphan Reaper] Failed to reap jobs: {e}")


def sweep_expired_outputs(max_age_seconds: int = 3600) -> None:
    """Deletes files in OUTPUT_DIR that are older than max_age_seconds (1 hour)."""
    if not OUTPUT_DIR.exists():
        return
    now = time.time()
    deleted_count = 0
    for file_path in OUTPUT_DIR.glob("*"):
        if file_path.is_file():
            try:
                age = now - file_path.stat().st_mtime
                if age > max_age_seconds:
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"[Sweeper] Failed to delete file {file_path.name}: {e}")
    if deleted_count > 0:
        print(f"[Sweeper] Deleted {deleted_count} expired files from output directory.")


async def output_sweeper_task() -> None:
    """Periodic background task that sweeps expired outputs every 15 minutes."""
    print("[Sweeper] Output file sweeper background task started.")
    while True:
        try:
            sweep_expired_outputs(max_age_seconds=3600)  # 1 hour expiration
        except Exception as e:
            print(f"[Sweeper task error] {e}")
        await asyncio.sleep(900)  # Sleep for 15 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    await reap_orphan_jobs()
    
    # Start periodic file sweeper if running in production
    is_prod = os.getenv("ENV") == "production" or os.getenv("PRODUCTION", "false").lower() == "true"
    if is_prod:
        asyncio.create_task(output_sweeper_task())
        print("[Lifespan] Production output sweeper task launched.")
    else:
        print("[Lifespan] Running in development mode: periodic file sweeper disabled.")
        
    yield

# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="SoundReverse API", version="2.0.0", lifespan=lifespan)

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

# ── Supabase client alias ─────────────────────────────────────────────────────

_get_supabase = get_supabase


# ── Track registry ────────────────────────────────────────────────────────────

TRACKS = [
    {"track_id": "billie_jean_mj",         "label": "Billie Jean — Michael Jackson",  "stress_test": False},
    {"track_id": "one_more_time_daft_punk", "label": "One More Time — Daft Punk",      "stress_test": False},
    {"track_id": "clocks_coldplay",         "label": "Clocks — Coldplay",              "stress_test": False},
    {"track_id": "humble_kendrick",         "label": "HUMBLE. — Kendrick Lamar",       "stress_test": True},
    {"track_id": "blinding_lights_weeknd",  "label": "Blinding Lights — The Weeknd",   "stress_test": False},
]


# ── Request model ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    user_input: str


# ── Background worker ─────────────────────────────────────────────────────────

def _build_result_payload(state: dict, api_base: str = "") -> dict:
    sig             = state["signal_signature"]
    settings        = state["producer_settings"]
    meta            = sig.metadata if sig else {}
    researcher_meta = state.get("researcher_metadata", {})
    musician_notes  = state.get("musician_notes")
    track_id        = state.get("_track_id", "unknown")
    job_id          = state.get("job_id")
    
    # Use job_id for namespacing filenames if present to avoid overwrite conflicts
    prefix = job_id if job_id else track_id

    return {
        "track": {
            "title":       researcher_meta.get("title") or meta.get("title", track_id),
            "artist":      researcher_meta.get("artist") or meta.get("artist", ""),
            "lufs":        sig.master.lufs  if sig else None,
            "bpm":         sig.rhythm.bpm   if sig else None,
            "key":         sig.rhythm.key   if sig else None,
            "youtube_url": state.get("youtube_url"),
        },
        "pipeline": {
            "confidence":           state["confidence"],
            "iteration_count":      state["iteration_count"],
            "max_iterations":       3,
            "critic_rounds":        state.get("critic_rounds", []),
            "validation_checks":    state.get("validation_checks", []),
            "researcher_reasoning": researcher_meta.get("reasoning"),
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


async def _run_job(job_id: str, user_input: str, stress_test: bool, api_base: str) -> None:
    sb = get_supabase()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({
            "status": "processing",
            "updated_at": now_iso
        }).eq("id", job_id).execute()

        # TODO(mcp-integration): real per-stage progress for the frontend loader.
        # The frontend currently cycles stage captions on a timer (cosmetic only).
        # To make it truthful once the Modal MCP is wired in (the slow step):
        #   1. Add a nullable `stage` text column to the `jobs` table.
        #   2. Pass an `on_stage(name)` callback into run_graph and invoke it from each
        #      LangGraph node (researcher / mcp / gateway / musician / analyst / critic),
        #      e.g. via LangGraph's streaming/callbacks, writing:
        #         sb.table("jobs").update({"stage": name}).eq("id", job_id).execute()
        #   3. Surface `stage` in GET /jobs/{id} (see placeholder there) and have the
        #      frontend poll drive the caption instead of the timer.
        # Run the graph synchronously in a background thread with a 180s timeout
        state = await asyncio.wait_for(
            asyncio.to_thread(run_graph, user_input, stress_test, job_id),
            timeout=180.0
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        if state.get("error"):
            sb.table("jobs").update({
                "status":        "failed",
                "error_message": state["error"],
                "updated_at":    now_iso
            }).eq("id", job_id).execute()
            return

        sb.table("jobs").update({
            "status":         "completed",
            "result_payload": _build_result_payload(state, api_base),
            "updated_at":    now_iso
        }).eq("id", job_id).execute()

    except asyncio.TimeoutError:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({
            "status":        "failed",
            "error_message": "Analysis timed out after 180 seconds.",
            "updated_at":    now_iso
        }).eq("id", job_id).execute()
    except Exception as exc:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("jobs").update({
            "status":        "failed",
            "error_message": str(exc),
            "updated_at":    now_iso
        }).eq("id", job_id).execute()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/tracks")
def get_tracks():
    return TRACKS


@app.post("/analyze", status_code=202)
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    stress_test = "humble" in req.user_input.lower()
    job_id      = str(uuid.uuid4())

    sb = get_supabase()
    sb.table("jobs").insert({
        "id":          job_id,
        "status":      "pending",
        "user_input":  req.user_input,
        "stress_test": stress_test,
    }).execute()

    api_base = os.getenv("API_BASE_URL", "")
    background_tasks.add_task(_run_job, job_id, req.user_input, stress_test, api_base)

    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    sb = get_supabase()
    response = sb.table("jobs").select("*").eq("id", job_id).single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")

    job = response.data
    out = {"job_id": job["id"], "status": job["status"]}

    # TODO(mcp-integration): expose live pipeline stage to the frontend loader.
    # Once _run_job writes a `stage` column (see placeholder there), surface it:
    #     if job.get("stage"):
    #         out["stage"] = job["stage"]
    if job["status"] == "completed":
        out["result"] = job["result_payload"]
    elif job["status"] == "failed":
        out["error"] = job["error_message"]

    return out
