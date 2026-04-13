import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.graph import GraphState

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _get_trace_url() -> str | None:
    """
    Attempt to retrieve the LangSmith trace URL from the current run context.
    Returns None if LangSmith is not configured or trace is unavailable.
    """
    try:
        from langsmith import Client
        client = Client()
        # The run URL is available via the LANGCHAIN_RUN_URL env var when tracing is active
        return os.environ.get("LANGCHAIN_RUN_URL")
    except Exception:
        return None


def output_node(state: "GraphState") -> "GraphState":
    if state.get("error"):
        return state

    settings = state["producer_settings"]
    track_id = state["track_request"].track_id
    trace_url = state.get("trace_url") or _get_trace_url()

    OUTPUT_DIR.mkdir(exist_ok=True)

    preset = {
        "track_id": track_id,
        "trace_url": trace_url,
        "confidence": state["confidence"],
        "iteration_count": state["iteration_count"],
        **settings.model_dump(),
    }

    preset_path = OUTPUT_DIR / f"{track_id}_preset.json"
    preset_path.write_text(json.dumps(preset, indent=2), encoding="utf-8")

    return {**state, "trace_url": trace_url}
