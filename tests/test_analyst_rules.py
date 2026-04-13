import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import pytest
from agents.analyst import _apply_rules
from schemas.signal_signature import SignalSignature, StemMetrics, MasterMetrics, RhythmMetrics

RULES = yaml.safe_load(
    (Path(__file__).parent.parent / "rules" / "rules.yaml").read_text(encoding="utf-8")
)["rules"]

RHYTHM = RhythmMetrics(bpm=120.0, bpm_confidence=0.9, key="C major", key_confidence=0.8, time_signature="4/4")
DRUMS_NO_KICK = StemMetrics(lufs=-14.0, peak_db=-3.0, dynamic_range_db=8.0, spectral_tilt=0.5, stereo_correlation=0.9)


def _master(lufs=-12.0, dr=7.0, tilt=0.5):
    return MasterMetrics(
        lufs=lufs, peak_db=-1.0, true_peak_dbtp=-0.5,
        dynamic_range_db=dr, spectral_tilt=tilt,
        stereo_correlation=0.8, stereo_width=0.6,
        low_energy_ratio=0.3, mid_energy_ratio=0.4, high_energy_ratio=0.3,
    )


def _sig(master=None, stems=None):
    return SignalSignature(
        track_id="test", metadata={},
        master=master or _master(),
        stems=stems or {"drums": DRUMS_NO_KICK},
        rhythm=RHYTHM,
    )


# ── Spectral tilt rules ──────────────────────────────────────────────────────

def test_spectral_tilt_bright_adds_high_shelf_cut():
    result = _apply_rules(_sig(master=_master(tilt=0.75)), RULES)
    bands = result["eq_bands"]
    assert any(b["band"] == "high_shelf" and b["gain_db"] < 0 for b in bands)


def test_spectral_tilt_dark_adds_high_shelf_boost():
    result = _apply_rules(_sig(master=_master(tilt=0.35)), RULES)
    bands = result["eq_bands"]
    assert any(b["band"] == "high_shelf" and b["gain_db"] > 0 for b in bands)


def test_spectral_tilt_neutral_no_high_shelf():
    result = _apply_rules(_sig(master=_master(tilt=0.55)), RULES)
    bands = result["eq_bands"]
    assert not any(b["band"] == "high_shelf" for b in bands)


# ── Kick fundamental rule ────────────────────────────────────────────────────

def test_kick_fundamental_boost_uses_actual_frequency():
    drums = StemMetrics(
        lufs=-14.0, peak_db=-3.0, dynamic_range_db=8.0,
        spectral_tilt=0.5, stereo_correlation=0.9,
        kick_fundamental_hz=62.0,
    )
    result = _apply_rules(_sig(stems={"drums": drums}), RULES)
    kick_band = next((b for b in result["eq_bands"] if b["band"] == "low_peak"), None)
    assert kick_band is not None
    assert kick_band["freq"] == 62


def test_no_kick_fundamental_no_low_peak_band():
    result = _apply_rules(_sig(stems={"drums": DRUMS_NO_KICK}), RULES)
    assert not any(b["band"] == "low_peak" for b in result["eq_bands"])


# ── Compression rules ────────────────────────────────────────────────────────

def test_heavy_compression_skip_when_dr_below_5():
    result = _apply_rules(_sig(master=_master(dr=3.0)), RULES)
    assert result["compression"] is None
    assert result["compression_reason_template"] is not None


def test_moderate_compression_applied_when_dr_between_5_and_10():
    result = _apply_rules(_sig(master=_master(dr=7.0)), RULES)
    assert result["compression"] is not None
    assert result["compression"]["ratio"] == "4:1"


# ── Master gain rules ────────────────────────────────────────────────────────

def test_loud_master_gain_is_zero():
    result = _apply_rules(_sig(master=_master(lufs=-8.0)), RULES)
    assert result["master_gain_db"] == 0


def test_quiet_master_gain_is_plus_three():
    result = _apply_rules(_sig(master=_master(lufs=-16.0)), RULES)
    assert result["master_gain_db"] == 3
