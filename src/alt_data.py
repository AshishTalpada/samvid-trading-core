class AltDataIngestor:
    """Ingests alternative datasets (satellites, credit cards)."""
    def ingest(self, source: str) -> dict:
        return {"signal": "NEUTRAL"}
