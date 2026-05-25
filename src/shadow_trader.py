import logging

logger = logging.getLogger(__name__)


class ShadowTrader:
    """
    Recursive Self-Play Engine. Agents trade against their own historical "ghosts".
    By competing against a snapshot of its own weights from 1 week ago,
    the model continuously forces parameter evolution and prevents strategy decay.
    """

    def __init__(self):
        self.ghost_pnl = 0.0
        self.current_pnl = 0.0

    def record_trade(self, current_model_return: float, ghost_model_return: float) -> None:
        self.current_pnl += current_model_return
        self.ghost_pnl += ghost_model_return

    def evaluate_evolution(self) -> float:
        edge = self.current_pnl - self.ghost_pnl
        if edge < 0:
            logger.warning(f"[SHADOW] Regressive Update: Ghost outperformed current by {-edge:.2%}")
        else:
            logger.info(f"[SHADOW] Evolution Positive: Current outperformed ghost by {edge:.2%}")
        return edge

    def trigger_rollback_if_needed(self) -> bool:
        if self.current_pnl < self.ghost_pnl - 0.05:  # 5% worse than ghost
            logger.critical("[SHADOW] FATAL DECAY DETECTED. Recommending weight rollback.")
            return True
        return False
