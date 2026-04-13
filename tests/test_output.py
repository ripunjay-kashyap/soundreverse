import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from output.generator import output_node
from schemas.producer_settings import Compression, EQBand, ProducerSettings
from schemas.signal_signature import SignalSignature, StemMetrics, MasterMetrics, RhythmMetrics
from schemas.track_request import TrackRequest

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _make_state(track_id="test_output_node", trace_url=None):
    master = MasterMetrics(
        lufs=-12.0, peak_db=-1.0, true_peak_dbtp=-0.5,
        dynamic_range_db=7.0, spectral_tilt=0.5,
        stereo_correlation=0.8, stereo_width=0.6,
        low_energy_ratio=0.3, mid_energy_ratio=0.4, high_energy_ratio=0.3,
    )
    drums = StemMetrics(
        lufs=-14.0, peak_db=-3.0, dynamic_range_db=8.0,
        spectral_tilt=0.5, stereo_correlation=0.9, kick_fundamental_hz=62.0,
    )
    rhythm = RhythmMetrics(
        bpm=120.0, bpm_confidence=0.9, key="C major",
        key_confidence=0.8, time_signature="4/4",
    )
    sig = SignalSignature(
        track_id=track_id,
        metadata={"title": "Test Track", "artist": "Test Artist"},
        master=master, stems={"drums": drums}, rhythm=rhythm,
    )
    settings = ProducerSettings(
        eq=[EQBand(band="high_shelf", freq=10000, gain_db=-2.5, reason="spectral_tilt=0.5")],
        compression=Compression(ratio="4:1", attack_ms=10, release_ms=80, reason="DR=7.0dB"),
        master_gain_db=0.0,
        confidence=1.0,
        iteration_count=1,
    )
    return {
        "track_request": TrackRequest(track_id=track_id, signal_signature=sig),
        "signal_signature": sig,
        "producer_settings": settings,
        "iteration_count": 1,
        "confidence": 1.0,
        "critique": "",
        "final": True,
        "error": None,
        "trace_url": trace_url,
        "_track_id": track_id,
    }


@pytest.fixture(autouse=True)
def cleanup():
    track_id = "test_output_node"
    yield
    for suffix in ["_preset.json", "_blueprint.pdf"]:
        (OUTPUT_DIR / f"{track_id}{suffix}").unlink(missing_ok=True)


def test_json_preset_is_created():
    output_node(_make_state())
    preset_path = OUTPUT_DIR / "test_output_node_preset.json"
    assert preset_path.exists()


def test_json_preset_contains_required_fields():
    output_node(_make_state(trace_url="https://smith.langchain.com/fake"))
    data = json.loads((OUTPUT_DIR / "test_output_node_preset.json").read_text())
    assert data["track_id"] == "test_output_node"
    assert data["confidence"] == 1.0
    assert data["iteration_count"] == 1
    assert data["trace_url"] == "https://smith.langchain.com/fake"
    assert "eq" in data
    assert "compression" in data


def test_pdf_blueprint_is_created():
    output_node(_make_state())
    pdf_path = OUTPUT_DIR / "test_output_node_blueprint.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_error_state_skips_output():
    state = _make_state()
    state["error"] = "something went wrong"
    output_node(state)
    assert not (OUTPUT_DIR / "test_output_node_preset.json").exists()
