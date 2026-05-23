from pydantic import BaseModel


class TuningTarget(BaseModel):
    element: str       # e.g. "Kick", "Bass", "Vocal presence"
    hz: float
    note: str          # nearest musical note, e.g. "B1"


class MusicianNotes(BaseModel):
    """Musician/producer-facing read of the track's signal, for non-technical users.

    Facts (tuning_targets, tonal_tags) are derived deterministically from the
    SignalSignature; the prose fields (tuning_tip, tonal_character) are phrased
    by the LLM and grounded in those facts.
    """
    tuning_targets: list[TuningTarget] = []
    tuning_tip: str = ""          # one plain-language line on how to use the targets
    tonal_tags: list[str] = []    # short labels, e.g. ["Bass-forward", "Warm", "Mono-solid"]
    tonal_character: str = ""     # 1-2 sentence plain-language description
