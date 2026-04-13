import json
from pathlib import Path
from typing import TYPE_CHECKING

from schemas.signal_signature import SignalSignature
from schemas.track_request import TrackRequest

if TYPE_CHECKING:
    from agents.graph import GraphState

CACHE_DIR = Path(__file__).parent.parent / "cache"


def gateway_node(state: "GraphState") -> "GraphState":
    track_id: str = state.get("_track_id", "")

    cache_path = CACHE_DIR / f"{track_id}.json"

    if not cache_path.exists():
        return {
            **state,
            "error": f"Track '{track_id}' not found in cache. Available: {[p.stem for p in CACHE_DIR.glob('*.json')]}",
            "final": True,
        }

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        sig = SignalSignature.model_validate(data)
        track_request = TrackRequest(track_id=track_id, signal_signature=sig)
        return {
            **state,
            "track_request": track_request,
            "signal_signature": sig,
            "error": None,
        }
    except Exception as exc:
        return {
            **state,
            "error": f"Failed to load '{track_id}': {exc}",
            "final": True,
        }
