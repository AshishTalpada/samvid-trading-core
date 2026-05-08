import logging
logger = logging.getLogger(__name__)

class TaxFormExporter:
    """Auto-generates IRS Form 8949 compatible data for capital gains reporting."""
    def export_8949(self, trades: list[dict]) -> list[dict]:
        rows = []
        for t in trades:
            rows.append({
                "description": t.get("ticker", "UNKNOWN"),
                "date_acquired": t.get("entry_date", ""),
                "date_sold": t.get("exit_date", ""),
                "proceeds": round(t.get("exit_value", 0.0), 2),
                "cost_basis": round(t.get("entry_value", 0.0), 2),
                "gain_loss": round(t.get("exit_value", 0.0) - t.get("entry_value", 0.0), 2),
            })
        logger.info(f"Exported {len(rows)} trades to Form 8949 format.")
        return rows
