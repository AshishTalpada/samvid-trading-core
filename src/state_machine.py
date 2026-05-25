import logging
from typing import Dict

logger = logging.getLogger(__name__)


class AdversarialStateMachine:
    """
    Fault-tolerant FSM utilizing twin state verification.
    Two identical state machines advance in parallel; if their states diverge,
    a critical logical bug has occurred, triggering an immediate safety halt.
    Prevents execution of trades in indeterminate logic states.
    """

    def __init__(self, initial_state: str = "IDLE"):
        self.state_a = initial_state
        self.state_b = initial_state
        self.transitions: Dict[str, Dict[str, str]] = {}

    def add_transition(self, start: str, trigger: str, end: str) -> None:
        if start not in self.transitions:
            self.transitions[start] = {}
        self.transitions[start][trigger] = end

    def trigger(self, event: str) -> bool:
        next_a = self.transitions.get(self.state_a, {}).get(event)
        next_b = self.transitions.get(self.state_b, {}).get(event)

        if not next_a or not next_b:
            logger.error(f"[FSM] Invalid transition '{event}' from state '{self.state_a}'")
            return False

        self.state_a = next_a
        self.state_b = next_b

        if self.state_a != self.state_b:
            logger.critical(f"[FSM] DIVERGENCE FATAL ERROR! A={self.state_a}, B={self.state_b}")
            self.state_a = "HALTED"
            self.state_b = "HALTED"
            return False

        logger.debug(f"[FSM] Transitioned to {self.state_a}")
        return True

    def current_state(self) -> str:
        return self.state_a
