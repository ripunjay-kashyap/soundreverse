import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.graph import GraphState

CACHE_DIR = Path(__file__).parent.parent / "cache"

def mcp_mock_node(state: "GraphState") -> "GraphState":
    """
    Mock MCP node: Simulates audio analysis by providing raw dict data to the state.
    """
    if state.get("error"):
        return state

    metadata = state.get("researcher_metadata") or {}
    title = metadata.get("title", "").lower()
    artist = metadata.get("artist", "").lower()
    slug = metadata.get("slug", "unknown_track")
    
    matched_track_id = None
    tracks = {
        "billie_jean": "billie_jean_mj",
        "humble": "humble_kendrick",
        "one_more_time": "one_more_time_daft_punk",
        "clocks": "clocks_coldplay",
        "blinding_lights": "blinding_lights_weeknd"
    }
    
    for key, track_id in tracks.items():
        if key in title or key in artist or key in slug:
            matched_track_id = track_id
            break
            
    if not matched_track_id:
        matched_track_id = "billie_jean_mj"
        print(f"\nMock MCP: No exact match found for '{title}' by '{artist}'. Defaulting signature to {matched_track_id}.")
    else:
        print(f"\nMock MCP: Matched signature to {matched_track_id}.")

    cache_path = CACHE_DIR / f"{matched_track_id}.json"
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if "metadata" not in data:
            data["metadata"] = {}
        data["metadata"]["title"] = metadata.get("title", data["metadata"].get("title", "Unknown Title"))
        data["metadata"]["artist"] = metadata.get("artist", data["metadata"].get("artist", "Unknown Artist"))
        
        # Override the track_id with our newly generated slug
        data["track_id"] = slug
        
        return {
            **state,
            "raw_mcp_output": data,
            "_track_id": slug
        }
    except Exception as e:
        return {**state, "error": f"Mock MCP failed to load signature: {str(e)}"}
