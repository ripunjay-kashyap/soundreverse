from typing import TYPE_CHECKING

from schemas.producer_settings import ProducerSettings
from schemas.signal_signature import SignalSignature

if TYPE_CHECKING:
    from agents.graph import GraphState

CONFIDENCE_THRESHOLD = 0.75
MAX_ITERATIONS = 3


def _run_checks(sig: SignalSignature, settings: ProducerSettings) -> tuple[float, list[str]]:
    """
    Run all physical-impossibility checks.
    Returns (confidence, list_of_failure_reasons).
    confidence = checks_passed / total_applicable_checks.
    """
    checks_passed = 0
    total = 0
    failures: list[str] = []

    # Check 1: over-compression — applying compression to an already slammed master
    total += 1
    if settings.compression is not None and sig.master.dynamic_range_db < 4:
        failures.append(
            f"Over-compression: compression applied but dynamic_range_db={sig.master.dynamic_range_db}dB < 4dB"
        )
    else:
        checks_passed += 1

    # Check 2: boosting a high shelf that is already bright
    high_shelf_boost = any(
        b.band == "high_shelf" and b.gain_db > 0
        for b in settings.eq
    )
    total += 1
    if high_shelf_boost and sig.master.spectral_tilt > 0.75:
        failures.append(
            f"Bright boost contradiction: high_shelf gain > 0 but spectral_tilt={sig.master.spectral_tilt} > 0.75"
        )
    else:
        checks_passed += 1

    # Check 3: pushing a master that is already at or above streaming ceiling
    total += 1
    if settings.master_gain_db > 0 and sig.master.lufs > -9:
        failures.append(
            f"Loudness ceiling breach: master_gain_db={settings.master_gain_db} > 0 but LUFS={sig.master.lufs} > -9"
        )
    else:
        checks_passed += 1

    # Check 4: kick boost frequency mismatch (only applicable if a kick EQ band exists)
    drums = sig.stems.get("drums")
    kick_band = next((b for b in settings.eq if b.band == "low_peak"), None)
    if kick_band is not None and drums is not None and drums.kick_fundamental_hz is not None:
        total += 1
        diff = abs(kick_band.freq - drums.kick_fundamental_hz)
        if diff > 20:
            failures.append(
                f"Kick freq mismatch: EQ targets {kick_band.freq}Hz but kick_fundamental_hz={drums.kick_fundamental_hz}Hz "
                f"(diff={diff:.1f}Hz > 20Hz)"
            )
        else:
            checks_passed += 1

    confidence = checks_passed / total if total > 0 else 1.0
    return round(confidence, 4), failures


def critic_node(state: "GraphState") -> "GraphState":
    sig: SignalSignature = state["signal_signature"]
    settings: ProducerSettings = state["producer_settings"]
    iteration_count: int = state.get("iteration_count", 0) + 1

    confidence, failures = _run_checks(sig, settings)

    settings = settings.model_copy(update={"confidence": confidence, "iteration_count": iteration_count})

    if confidence >= CONFIDENCE_THRESHOLD or iteration_count >= MAX_ITERATIONS:
        critique_note = ""
        if iteration_count >= MAX_ITERATIONS and confidence < CONFIDENCE_THRESHOLD:
            critique_note = f" (max iterations reached, signing off with confidence={confidence})"
        return {
            **state,
            "producer_settings": settings,
            "confidence": confidence,
            "iteration_count": iteration_count,
            "critique": "; ".join(failures) + critique_note,
            "final": True,
        }

    critique = "; ".join(failures)
    return {
        **state,
        "producer_settings": settings,
        "confidence": confidence,
        "iteration_count": iteration_count,
        "critique": critique,
        "final": False,
    }
