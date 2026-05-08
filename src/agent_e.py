"""
src/agent_e.py - Sector Correlation Guard
Prevents portfolio over-exposure to a single market sector.
Implements rule: Max 30% allocation per sector.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CorrelationGuard:
    def __init__(self, max_sector_exposure: float = 0.30) -> None:
        self.max_sector_exposure = max_sector_exposure
        self.persist_path = "data/sector_map.json"

        # Base Institutional Sector Map
        self.sector_map = {
            "AAPL": "TECH",
            "MSFT": "TECH",
            "GOOGL": "TECH",
            "NVDA": "TECH",
            "AMD": "TECH",
            "AVGO": "TECH",
            "SMCI": "TECH",
            "ARM": "TECH",
            "PLTR": "TECH",
            "ADBE": "TECH",
            "NFLX": "CONSUMER",
            "JPM": "FINANCE",
            "GS": "FINANCE",
            "V": "FINANCE",
            "MA": "FINANCE",
            "MSTR": "CRYPTO",
            "COIN": "CRYPTO",
            "MARA": "CRYPTO",
            "RIOT": "CRYPTO",
            "TSLA": "AUTO",
            "WMT": "RETAIL",
            "COST": "RETAIL",
            "SPY": "INDEX",
            "QQQ": "INDEX",
            "IWM": "INDEX",
            "DIA": "INDEX",
            "TLT": "BONDS",
            "GLD": "COMMODITY",
            "USO": "COMMODITY",
        }
        self._load_map()

    def _load_map(self) -> None:
        """Load persisted sector map from disk, merging with defaults."""
        import json
        import os

        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "r") as f:
                    disk_map = json.load(f)
                    self.sector_map.update(disk_map)
                    logger.info(f"CORRELATION: Loaded {len(disk_map)} sectors from disk.")
            except Exception as e:
                logger.error(f"CORRELATION: Map load failure: {e}")

    def _save_map(self) -> None:
        """Persist discovered sectors to disk for continuity across restarts."""
        import json
        import os

        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            # Only save the non-default ones to keep it clean?
            # Or just save everything. Everything is safer.
            with open(self.persist_path, "w") as f:
                json.dump(self.sector_map, f, indent=4)
        except Exception as e:
            logger.error(f"CORRELATION: Map save failure: {e}")

    async def get_sector(self, symbol: str) -> str:
        """Get the sector for a symbol with dynamic fallback."""
        s = symbol.upper()
        if s in self.sector_map:
            return self.sector_map[s]

        try:
            import asyncio

            import yfinance as yf

            def _fetch_yf():
                ticker = yf.Ticker(s)
                info = ticker.info
                if not info:
                    return None
                return info.get("sector") or info.get("industry") or "OTHER"

            sector = await asyncio.to_thread(_fetch_yf)
            if sector:
                sector = sector.upper().replace(" ", "_")
                self.sector_map[s] = sector
                self._save_map()
                logger.info(f"CORRELATION: Discovered {s} as {sector}")
                return sector
        except Exception as e:
            logger.debug(f"Dynamic sector discovery failed for {s}: {e}")

        return "OTHER"

    async def check_exposure(
        self,
        symbol: str,
        current_positions: list,
        account_value: float,
        new_position_value: float = 0.0,
    ) -> bool:
        """
        Check if adding the new symbol would exceed sector exposure limits.
        """
        if account_value <= 0:
            return False

        target_sector = await self.get_sector(symbol)
        if target_sector == "INDEX":
            return True  # Indices are allowed to have higher exposure usually

        sector_value = 0.0
        for pos in current_positions:
            pos_symbol = (
                pos.get("symbol", "") if isinstance(pos, dict) else getattr(pos, "symbol", "")
            )
            # --- RISK ACCURACY UPDATE ---
            # Use current market price if available, otherwise fallback to entry_price
            pos_price = (
                pos.get("current_price", 0)
                if isinstance(pos, dict)
                else getattr(pos, "current_price", 0)
            )
            if pos_price <= 0:
                pos_price = (
                    pos.get("entry_price", 0)
                    if isinstance(pos, dict)
                    else getattr(pos, "entry_price", 0)
                )

            pos_qty = pos.get("qty", 0) if isinstance(pos, dict) else getattr(pos, "qty", 0)
            if (await self.get_sector(pos_symbol)) == target_sector:
                sector_value += float(pos_price) * float(pos_qty)  # type: ignore

        # Resulting exposure IF WE ADDED the new position
        exposure_pct = (sector_value + new_position_value) / account_value

        limit = min(self.max_sector_exposure, 0.30)
        if exposure_pct >= limit:
            logger.warning(
                f"CORRELATION GUARD: Rejection! Sector {target_sector} would reach {exposure_pct:.1%} (Limit: {limit:.1%})"
            )
            return False

        return True

    async def get_current_exposures(
        self, current_positions: list, account_value: float
    ) -> dict[str, float]:
        """Returns a dict of current sector exposures for the Cockpit."""
        if account_value <= 0:
            return {}

        exposures = {}
        for pos in current_positions:
            pos_symbol = (
                pos.get("symbol", "") if isinstance(pos, dict) else getattr(pos, "symbol", "")
            )
            # Market value exposure tracking
            pos_price = (
                pos.get("current_price", 0)
                if isinstance(pos, dict)
                else getattr(pos, "current_price", 0)
            )
            if pos_price <= 0:
                pos_price = (
                    pos.get("entry_price", 0)
                    if isinstance(pos, dict)
                    else getattr(pos, "entry_price", 0)
                )

            pos_qty = pos.get("qty", 0) if isinstance(pos, dict) else getattr(pos, "qty", 0)
            sector = await self.get_sector(pos_symbol)
            exposures[sector] = exposures.get(sector, 0.0) + (float(pos_price) * float(pos_qty))

        return {s: v / account_value for s, v in exposures.items()}

    async def evaluate_proposal(
        self, context: Dict[str, Any], agent_name: str = "Agent_E"
    ) -> Dict[str, Any]:
        """
        Provides Agent E's correlation-based vote.
        """

        symbol = context.get("symbol", "UNKNOWN")
        positions = context.get("positions", [])
        account_value = context.get("account_value", 0.0)
        new_value = context.get("new_position_value", 0.0)

        target_sector = await self.get_sector(symbol)
        is_safe = await self.check_exposure(symbol, positions, account_value, new_value)

        vote = "YES" if is_safe else "NO"
        # If we are close to the limit (e.g. 25% vs 30%), lower confidence.
        # This signals 'Thin Ice' to the Coordinator.
        confidence = 1.0
        if is_safe:
            target_sector = await self.get_sector(symbol)
            # Recalculate exposure to get the actual %
            # (This is slightly redundant but ensures confidence accuracy)
            sector_value = 0.0
            for pos in positions:
                p_sym = (
                    pos.get("symbol", "") if isinstance(pos, dict) else getattr(pos, "symbol", "")
                )
                p_price = (
                    pos.get("current_price", 0)
                    if isinstance(pos, dict)
                    else getattr(pos, "current_price", 0)
                )
                p_qty = pos.get("qty", 0) if isinstance(pos, dict) else getattr(pos, "qty", 0)
                if (await self.get_sector(p_sym)) == target_sector:
                    sector_value += float(p_price) * float(p_qty)

            exposure_pct = float(sector_value + new_value) / float(account_value or 1)
            limit = min(self.max_sector_exposure, 0.30)
            if exposure_pct > (limit * 0.8):  # Above 24% exposure
                confidence = 0.65  # Thin ice

        reason = f"Sector: {target_sector} | "
        if is_safe:
            reason += "Exposure within limits."
        else:
            reason += "VETO: Sector exposure limit exceeded!"

        return {
            "agent": agent_name,
            "vote": vote,
            "confidence": confidence,
            "signal_strength": 1.0,
            "risk_flag": not is_safe or confidence < 0.7,
            "reason": reason,
            "sector": target_sector,
        }
