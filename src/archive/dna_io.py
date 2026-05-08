import hashlib
import logging

logger = logging.getLogger(__name__)

BASE_MAP = {'00': 'A', '01': 'C', '10': 'G', '11': 'T'}
DECODE_MAP = {v: k for k, v in BASE_MAP.items()}

class DNAArchiveIO:
    """
    DNA-based data encoding for theoretical 10,000-year archival storage.
    Encodes binary data as DNA nucleotide sequences (A/C/G/T).
    Production: interfaces with Twist Bioscience synthesis API.
    Simulation: encodes/decodes as nucleotide strings for verification.
    """
    def encode(self, data: bytes) -> str:
        bits = bin(int(data.hex(), 16))[2:].zfill(len(data) * 8)
        pairs = [bits[i:i+2] for i in range(0, len(bits), 2)]
        dna = "".join(BASE_MAP.get(p, 'A') for p in pairs)
        checksum = hashlib.sha3_256(data).hexdigest()[:8]
        logger.info(f"[DNA IO] Encoded {len(data)} bytes -> {len(dna)} bases. Checksum={checksum}")
        return dna + checksum

    def decode(self, dna_sequence: str) -> bytes:
        dna, checksum = dna_sequence[:-8], dna_sequence[-8:]
        bits = "".join(DECODE_MAP.get(c, '00') for c in dna)
        n = len(bits) // 8
        data = bytes(int(bits[i*8:(i+1)*8], 2) for i in range(n))
        actual = hashlib.sha3_256(data).hexdigest()[:8]
        if actual != checksum:
            raise ValueError(f"[DNA IO] Checksum mismatch: expected={checksum}, got={actual}")
        return data
