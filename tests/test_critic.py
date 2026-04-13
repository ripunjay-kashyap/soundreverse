import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.critic import _run_checks, critic_node
from schemas.producer_settings import Compression, EQBand, ProducerSettings
from schemas.signal_signature import SignalSignature, StemMetrics, MasterMetrics, RhythmMetrics

RHYTHM = RhythmMetrics(bpm=120.0, bpm_confidence=0.9, key="C major", key_confidence=0.8, time_signature="4/4")


def _master(lufs=-12.0, dr=7.0, tilt=0.5):
    return MasterMetrics(
        lufs=lufs, peak_db=-1.0, true_peak_dbtp=-0.5,
        dynamic_range_db=dr, spectral_tilt=tilt,
        stereo_correlation=0.8, stereo_width=0.6,
        low_energy_ratio=0.3, mid_energy_ratio=0.4, high_energy_ratio=0.3,
    )


def _sig(master=None, kick_hz=None):
    drums = StemMetrics(
        lufs=-14.0, peak_db=-3.0, dynamic_range_db=8.0,
        spectral_tilt=0.5, stereo_correlation=0.9,
        kick_fundamental_hz=kick_hz,
    )
    return SignalSignature(
        track_id="test", metadata={},
        master=master or _master(),
        stems={"drums": drums},
        rhythm=RHYTHM,
    )


def _settings(compression=None, master_gain=0.0, eq=None):
    return ProducerSettings(
        eq=eq or [],
        compression=compression,
        master_gain_db=master_gain,
    )


def _compression():
    return Compression(ratio="4:1", attack_ms=10, release_ms=80, reason="test")


def _high_shelf(gain_db):
    return EQBand(band="high_shelf", freq=10000, gain_db=gain_db, reason="test")


def _kick_band(freq):
    return EQBand(band="low_peak", freq=freq, gain_db=2.0, q=1.2, reason="test")


# ── All checks pass ──────────────────────────────────────────────────────────

def test_all_checks_pass_gives_confidence_1():
    sig = _sig(master=_master(lufs=-12.0, dr=7.0, tilt=0.5))
    settings = _settings()
    confidence, failures = _run_checks(sig, settings)
    assert confidence == 1.0
    assert failures == []


# ── Over-compression ─────────────────────────────────────────────────────────

def test_over_compression_flagged_when_dr_below_4():
    sig = _sig(master=_master(dr=3.0))
    settings = _settings(compression=_compression())
    confidence, failures = _run_checks(sig, settings)
    assert any("over-compression" in f.lower() or "compression" in f.lower() for f in failures)
    assert confidence < 1.0


def test_compression_allowed_when_dr_above_4():
    sig = _sig(master=_master(dr=5.0))
    settings = _settings(compression=_compression())
    confidence, failures = _run_checks(sig, settings)
    assert not any("compression" in f.lower() for f in failures)


# ── Bright boost contradiction ────────────────────────────────────────────────

def test_high_shelf_boost_on_bright_mix_flagged():
    sig = _sig(master=_master(tilt=0.8))
    settings = _settings(eq=[_high_shelf(gain_db=+1.5)])
    confidence, failures = _run_checks(sig, settings)
    assert any("bright" in f.lower() or "spectral_tilt" in f.lower() for f in failures)
    assert confidence < 1.0


def test_high_shelf_cut_on_bright_mix_passes():
    sig = _sig(master=_master(tilt=0.8))
    settings = _settings(eq=[_high_shelf(gain_db=-2.5)])
    confidence, failures = _run_checks(sig, settings)
    assert not any("spectral_tilt" in f.lower() for f in failures)


# ── Loudness ceiling ─────────────────────────────────────────────────────────

def test_master_gain_boost_on_loud_track_flagged():
    sig = _sig(master=_master(lufs=-8.0))
    settings = _settings(master_gain=+2.0)
    confidence, failures = _run_checks(sig, settings)
    assert any("lufs" in f.lower() or "loudness" in f.lower() for f in failures)
    assert confidence < 1.0


def test_master_gain_boost_on_quiet_track_passes():
    sig = _sig(master=_master(lufs=-16.0))
    settings = _settings(master_gain=+3.0)
    confidence, failures = _run_checks(sig, settings)
    assert not any("loudness" in f.lower() for f in failures)


# ── Kick frequency mismatch ───────────────────────────────────────────────────

def test_kick_freq_mismatch_over_20hz_flagged():
    sig = _sig(kick_hz=60.0)
    settings = _settings(eq=[_kick_band(freq=90)])  # 30Hz off
    confidence, failures = _run_checks(sig, settings)
    assert any("kick" in f.lower() or "freq" in f.lower() for f in failures)
    assert confidence < 1.0


def test_kick_freq_within_20hz_passes():
    sig = _sig(kick_hz=60.0)
    settings = _settings(eq=[_kick_band(freq=65)])  # 5Hz off
    confidence, failures = _run_checks(sig, settings)
    assert not any("kick" in f.lower() for f in failures)


# ── Iteration cap ─────────────────────────────────────────────────────────────

def test_critic_node_signs_off_at_max_iterations():
    sig = _sig(master=_master(dr=3.0))  # will fail over-compression check
    settings = _settings(compression=_compression())
    state = {
        "signal_signature": sig,
        "producer_settings": settings,
        "iteration_count": 2,  # critic will increment to 3 → max reached
        "confidence": 0.0,
        "critique": "",
        "final": False,
        "track_request": None,
        "error": None,
        "trace_url": None,
        "_track_id": "test",
    }
    result = critic_node(state)
    assert result["final"] is True
    assert result["iteration_count"] == 3
