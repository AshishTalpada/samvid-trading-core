import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

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
    symbol: str
    qty: float
    entry_price: float
    entry_time: datetime
    pattern: str
    initial_belief: float
    current_belief: float
    initial_stop: float
    stop_loss: float
    take_profit: float
    account_type: str
    trade_id: str
    task_id: str = "NONE"
    catalyst_score: float = 0.5
    regime_at_entry: str = "UNKNOWN"
    commission_cost: float = 0.0
    slippage_cost: float = 0.0
    mfe: float = 0.0
    mae: float = 0.0
    unrealized_pnl: float = 0.0
    current_price: float = 0.0
    status: str = "OPEN"
    meta: Dict = field(default_factory=dict)
    target_exit_time: Optional[datetime] = None
    account_id: str = "UNKNOWN"
    dhatu_state: str = "UNKNOWN"
    r_r_ratio: float = 2.0

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

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
