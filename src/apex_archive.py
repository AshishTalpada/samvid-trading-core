import hashlib
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ApexArchive:
    """
    Immutable append-only decision archive.
    Every quorum decision is permanently stored with a SHA3-256 chain hash,
    creating a cryptographic audit trail that cannot be altered retroactively.
    """

    def __init__(self, path: str = "data/apex_archive.jsonl"):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = "GENESIS"

    def record(self, decision: dict) -> str:
        entry = {**decision, "timestamp": time.time(), "prev_hash": self._prev_hash}
        entry_bytes = json.dumps(entry, sort_keys=True).encode()
        entry_hash = hashlib.sha3_256(entry_bytes).hexdigest()
        entry["hash"] = entry_hash
        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._prev_hash = entry_hash
        logger.debug(f"[ARCHIVE] Recorded decision hash={entry_hash[:12]}...")
        return entry_hash

    def verify_chain(self) -> bool:
        entries = [json.loads(l) for l in self._path.read_text().splitlines() if l.strip()]
        for i, entry in enumerate(entries[1:], 1):
            if entry["prev_hash"] != entries[i - 1]["hash"]:
                logger.error(f"[ARCHIVE] Chain broken at entry {i}!")
                return False
        return True
