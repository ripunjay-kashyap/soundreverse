from typing import TYPE_CHECKING
from schemas.signal_signature import SignalSignature
from schemas.track_request import TrackRequest

if TYPE_CHECKING:
    from agents.graph import GraphState

def gateway_node(state: "GraphState") -> "GraphState":
    """
    Gateway node: Validates the raw MCP output against the SignalSignature schema.
    """
    if state.get("error"):
        return state

    raw_data = state.get("raw_mcp_output")
    track_id = state.get("_track_id", "unknown_track")

    if not raw_data:
        return {
            **state,
            "error": "No raw_mcp_output provided to Gateway.",
            "final": True,
        }

    try:
        sig = SignalSignature.model_validate(raw_data)
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
            "error": f"Gateway schema validation failed for '{track_id}': {exc}",
            "final": True,
        }
