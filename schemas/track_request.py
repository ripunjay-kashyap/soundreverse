from pydantic import BaseModel
from schemas.signal_signature import SignalSignature


class TrackRequest(BaseModel):
    track_id: str
    signal_signature: SignalSignature
