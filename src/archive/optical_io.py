import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OpticalArchiveIO:
    """
    Optical storage archive interface for Apex Archive holographic memory.
    Production: interfaces with Sony ODS (Optical Disc System) or Millenniata M-DISC.
    Simulation: uses append-only flat-file archive with CRC32 integrity verification.
    """

    import zlib

    def __init__(self, archive_path: str = "data/optical_archive.dat"):
        self._path = Path(archive_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write_record(self, data: dict) -> int:
        import zlib

        payload = json.dumps(data, sort_keys=True).encode()
        crc = zlib.crc32(payload)
        record = f"{crc}:{payload.decode()}\n"
        with open(self._path, "a") as f:
            f.write(record)
        logger.debug(f"[OPTICAL IO] Written record CRC={crc:08x}")
        return crc

    def verify_all(self) -> tuple[int, int]:
        import zlib

        ok, bad = 0, 0
        for line in self._path.read_text().splitlines():
            if ":" not in line:
                continue
            crc_str, payload = line.split(":", 1)
            expected = int(crc_str)
            actual = zlib.crc32(payload.encode())
            if expected == actual:
                ok += 1
            else:
                bad += 1
        logger.info(f"[OPTICAL IO] Verify: {ok} OK, {bad} CORRUPT")
        return ok, bad
