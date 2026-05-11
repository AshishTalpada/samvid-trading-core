from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

# --- INSTITUTIONAL SCHEMA PARITY (D-DRIVE) ---

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SSHORT = "SSHORT"

class OrderType(str, Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    STP_LMT = "STP_LMT"

class TradePhase(str, Enum):
    ENTRY = "ENTRY"
    MANAGEMENT = "MANAGEMENT"
    EXIT = "EXIT"
    AUDIT = "AUDIT"

# Deep Dive: Extreme Static Typing & Schema Definition
# These schemas enforce strict type boundaries across the entire system, preventing
# silent failures, NoneType exceptions, and runtime crashes during high-volatility execution.

@dataclass
class MarketTick:
    symbol: str
    bid: float
    ask: float
    volume: float
    timestamp_ns: int
    exchange: str

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid_price(self) -> float:
        return (self.ask + self.bid) / 2.0

@dataclass
class Position:
    """
    Sovereign Position-State Entity.
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
    target_exit_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=5))
    trade_id: str = ""
    account_type: str = "ibkr"
    account_id: str = "UNKNOWN"
    catalyst_score: float = 0.0
    dhatu_state: str = "UNKNOWN"
    regime_at_entry: str = "UNKNOWN"
    r_r_ratio: float = 2.0
    sl_pct: float = 0.01
    tp_pct: float = 0.02
    shares_remaining: float = 0.0
    commission_cost: float = 0.0
    slippage_cost: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    mfe: float = 0.0
    mae: float = 0.0
    runner_active: bool = False
    unrealized_pnl: float = 0.0
    current_price: float = 0.0
    db_id: int = 0
    status: str = "OPEN"
    task_id: str = "N/A"
    meta: Dict = field(default_factory=dict)

    def __post_init__(self):
        # If the position is live (qty != 0) but tracking is 0, sync them.
        if self.shares_remaining == 0.0 and self.qty != 0.0:
            self.shares_remaining = abs(self.qty)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

@dataclass
class OrderIntent:
    symbol: str
    side: str # "BUY" or "SELL"
    size_units: float
    target_price: float
    logic_signature: str # Which neural agent/quorum authorized this?
    intent_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ExecutionFill:
    intent_id: str
    ticket_id: str
    fill_price: float
    fill_qty: float
    slippage_bps: float
    commission: float
    timestamp_ms: int
    is_partial: bool = False

@dataclass
class RiskState:
    current_drawdown_pct: float
    daily_realized_pnl: float
    open_exposure_usd: float
    value_at_risk_99: float
    is_quarantined: bool = False
    active_circuit_breakers: List[str] = field(default_factory=list)

@dataclass
class AgentVote:
    agent_id: str
    vote: str # "BUY", "SELL", "HOLD"
    confidence: float # 0.0 to 1.0
    computation_time_ms: float
    mathematical_justification: str # E.g., "Hurst exponent = 0.72"
