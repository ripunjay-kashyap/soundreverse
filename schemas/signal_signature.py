import json
import sys
from pathlib import Path
from pydantic import BaseModel


class StemMetrics(BaseModel):
    lufs: float
    peak_db: float
    dynamic_range_db: float
    spectral_tilt: float
    stereo_correlation: float
    # drums stem only
    kick_fundamental_hz: float | None = None
    snare_fundamental_hz: float | None = None
    transient_sharpness: float | None = None
    # bass + vocals stems
    fundamental_hz: float | None = None
    # vocals stem only
    presence_peak_hz: float | None = None


class MasterMetrics(BaseModel):
    lufs: float
    peak_db: float
    true_peak_dbtp: float
    dynamic_range_db: float
    spectral_tilt: float
    stereo_correlation: float
    stereo_width: float
    low_energy_ratio: float
    mid_energy_ratio: float
    high_energy_ratio: float


class RhythmMetrics(BaseModel):
    bpm: float
    bpm_confidence: float
    key: str
    key_confidence: float
    time_signature: str


class SignalSignature(BaseModel):
    track_id: str
    metadata: dict
    stems: dict[str, StemMetrics]
    master: MasterMetrics
    rhythm: RhythmMetrics


# ── CLI validation helper ────────────────────────────────────────────────────

def _validate_all() -> None:
    cache_dir = Path(__file__).parent.parent / "cache"
    files = list(cache_dir.glob("*.json"))
    if not files:
        print("No cache files found.")
        sys.exit(1)

    passed = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            SignalSignature.model_validate(data)
            print(f"  OK  {path.name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {path.name}: {exc}")

    print(f"\n{passed}/{len(files)} cache files valid.")
    if passed < len(files):
        sys.exit(1)


if __name__ == "__main__":
    if "--validate-all" in sys.argv:
        _validate_all()
