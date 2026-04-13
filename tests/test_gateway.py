import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agents.gateway import gateway_node


BASE_STATE = {
    "track_request": None,
    "signal_signature": None,
    "producer_settings": None,
    "iteration_count": 0,
    "confidence": 0.0,
    "critique": "",
    "final": False,
    "error": None,
    "trace_url": None,
}


def test_cache_hit_loads_signal_signature():
    state = gateway_node({**BASE_STATE, "_track_id": "blinding_lights_weeknd"})

    assert state["error"] is None
    assert state["signal_signature"] is not None
    assert state["signal_signature"].track_id == "blinding_lights_weeknd"
    assert state["track_request"] is not None
    assert state["track_request"].track_id == "blinding_lights_weeknd"


def test_cache_miss_returns_error_without_crashing():
    state = gateway_node({**BASE_STATE, "_track_id": "does_not_exist"})

    assert state["error"] is not None
    assert "does_not_exist" in state["error"]
    assert state["final"] is True
    assert state["signal_signature"] is None
