from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"


class TradePhase(Enum):
    DISCOVERY = "DISCOVERY"
    ANALYSIS = "ANALYSIS"
    VETTING = "VETTING"
    CALIBRATION = "CALIBRATION"
    EXECUTION = "EXECUTION"
    LEARNING = "LEARNING"


@dataclass
class Position:
    """
    Sovereign Position-State Entity (SETO V8.0 Hardening).
    Decoupled from Brain/Coordinator to prevent circular imports.
    """

    symbol: str
    qty: float
    entry_price: float
    entry_time: datetime
    pattern: str = ""
    initial_belief: float = 0.5
    current_belief: float = 0.5
    initial_stop: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    target_exit_time: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=5))
    trade_id: str = ""
    account_type: str = "ibkr"
    account_id: str = "UNKNOWN"
    catalyst_score: float = 0.0
    dhatu_state: str = "UNKNOWN"
    regime_at_entry: str = "UNKNOWN"
    r_r_ratio: float = 2.0
    sl_pct: float = 0.01
    tp_pct: float = 0.02

    # --- TRUE COST TRACKING (SETO V8.0) ---
    shares_remaining: float = 0.0
    commission_cost: float = 0.0
    slippage_cost: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    mfe: float = 0.0
    mae: float = 0.0
    runner_active: bool = False
    # --- REAL-TIME STATE (SETO V21.40) ---
    unrealized_pnl: float = 0.0
    current_price: float = 0.0
    
    db_id: int = 0 # Persistent DB RowID for precision tracking (SETO V21.22)

    status: str = "OPEN"
    task_id: str = "N/A"
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # GAP-211 FIX: Handle legacy rows where shares_remaining is missing or 0
        # If the position is live (qty != 0) but tracking is 0, sync them.
        # GAP-199: Support negative qty for SHORT positions.
        if self.shares_remaining == 0.0 and self.qty != 0.0:
            self.shares_remaining = abs(self.qty)

