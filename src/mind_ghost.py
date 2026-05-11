import logging
import time
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class GhostExecutionEnvironment:
    '''
    Deep Dive: The Ghost Protocol.
    A completely isolated shadow-execution environment. When Sovereign comes up with
    a highly experimental trading strategy (low confidence), it routes it to the Ghost Environment
    instead of the real Broker Arbitrator. The Ghost environment simulates slippage, liquidity
    impact, and queue positions to track how the trade *would* have performed.
    '''
    def __init__(self, **kwargs):
        self.ghost_ledger: Dict[str, dict] = {}
        self.active_ghost_positions: Dict[str, dict] = {}
        self.heartbeats: Dict[str, float] = {}
        # Simulate institutional commission: $0.005 per share, min $1.00
        self.commission_per_share = 0.005
        self.min_commission = 1.00

    async def update_heartbeat(self, component: str):
        '''
        Records a heartbeat for a specific ghost component.
        '''
        self.heartbeats[component] = time.time()
        logger.debug(f"[GHOST] Heartbeat updated for {component}")

    async def start(self):
        '''Launch Agent J (Shadow Environment).'''
        logger.info("[GHOST] Ghost Protocol ENGAGED. Shadow execution environment online.")

    def _calculate_commission(self, size: float) -> float:
        return max(self.min_commission, size * self.commission_per_share)

    def route_shadow_trade(self, symbol: str, action: str, price: float, size: float, logic_signature: str) -> str:
        '''
        Ingests a trade intent and immediately fills it in the local shadow memory.
        '''
        trade_id = f"GHOST-{uuid.uuid4().hex[:8]}"

        # Simulate slippage based on size (simplified linear impact)
        simulated_slippage = (size / 100.0) * 0.0001
        fill_price = price * (1.0 + simulated_slippage) if action == "BUY" else price * (1.0 - simulated_slippage)
        
        commission = self._calculate_commission(size)

        position = {
            "symbol": symbol,
            "action": action,
            "fill_price": fill_price,
            "size": size,
            "logic_signature": logic_signature,
            "timestamp": time.time(),
            "unrealized_pnl": -commission, # Start down by commission
            "entry_commission": commission
        }

        self.active_ghost_positions[trade_id] = position
        logger.info(f"[GHOST] Shadow trade {trade_id} executed on {symbol}. Fill: {fill_price:.2f} (Comm: ${commission:.2f})")
        return trade_id

    def update_ghost_pnl(self, current_market_prices: Dict[str, float]):
        '''
        Continuously mark-to-market the active shadow positions.
        '''
        for trade_id, pos in self.active_ghost_positions.items():
            sym = pos["symbol"]
            if sym in current_market_prices:
                current_price = current_market_prices[sym]
                if pos["action"] == "BUY":
                    pnl = (current_price - pos["fill_price"]) * pos["size"]
                else:
                    pnl = (pos["fill_price"] - current_price) * pos["size"]

                # Account for entry commission
                pos["unrealized_pnl"] = pnl - pos["entry_commission"]

    def close_shadow_trade(self, trade_id: str, current_price: float) -> float:
        '''Closes a ghost position and permanently logs its realized PnL.'''
        if trade_id not in self.active_ghost_positions:
            return 0.0

        pos = self.active_ghost_positions.pop(trade_id)

        # Simulate closing slippage
        simulated_slippage = (pos["size"] / 100.0) * 0.0001
        close_price = current_price * (1.0 - simulated_slippage) if pos["action"] == "BUY" else current_price * (1.0 + simulated_slippage)
        
        exit_commission = self._calculate_commission(pos["size"])

        if pos["action"] == "BUY":
            gross_pnl = (close_price - pos["fill_price"]) * pos["size"]
        else:
            gross_pnl = (pos["fill_price"] - close_price) * pos["size"]

        realized_pnl = gross_pnl - pos["entry_commission"] - exit_commission
        pos["realized_pnl"] = realized_pnl
        pos["exit_commission"] = exit_commission
        pos["close_time"] = time.time()

        self.ghost_ledger[trade_id] = pos
        logger.info(f"[GHOST] Closed {trade_id}. Realized Net PnL: ${realized_pnl:.2f}")

        # Prune ledger in batches when limit is reached
        if len(self.ghost_ledger) > 1000:
            # Remove oldest 100 entries
            ids_to_prune = list(self.ghost_ledger.keys())[:100]
            for pid in ids_to_prune:
                self.ghost_ledger.pop(pid, None)
            logger.debug(f"[GHOST] Pruned 100 entries from ledger. Current size: {len(self.ghost_ledger)}")

        return realized_pnl

MindGhost = GhostExecutionEnvironment
