import sys
import json
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.signal_signature import SignalSignature

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_FILES = list(CACHE_DIR.glob("*.json"))

@pytest.mark.parametrize("file_path", CACHE_FILES, ids=lambda p: p.name)
def test_cache_file_conforms_to_signal_signature(file_path):
    assert file_path.exists()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    
    # This will raise a ValidationError if the data doesn't conform
    sig = SignalSignature.model_validate(data)
    
    # Perform basic structural sanity checks
    assert sig.track_id is not None
    assert sig.master is not None
    assert sig.rhythm is not None
    assert len(sig.stems) > 0
    assert "drums" in sig.stems
    assert "bass" in sig.stems
    assert "vocals" in sig.stems
    assert "other" in sig.stems
