from pydantic import BaseModel


class EQBand(BaseModel):
    band: str
    freq: int
    gain_db: float
    q: float | None = None
    reason: str


class Compression(BaseModel):
    ratio: str
    attack_ms: int
    release_ms: int
    reason: str


class ProducerSettings(BaseModel):
    eq: list[EQBand]
    compression: Compression | None
    master_gain_db: float
    confidence: float | None = None
    iteration_count: int = 0
