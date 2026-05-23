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
    # The uploaded filename is the source of truth for the display title.
    title = Path(filename).stem
    sig.setdefault("metadata", {})
    sig["metadata"]["title"] = title
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
