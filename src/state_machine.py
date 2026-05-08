from typing import Callable, Dict, Optional

class SovereignFSM:
    """Adversarial finite state machine ensuring all state transitions are valid."""
    def __init__(self, initial_state: str):
        self.state = initial_state
        self.transitions: Dict[str, Dict[str, Callable]] = {}

    def add_transition(self, from_state: str, event: str, to_state: str,
                       action: Optional[Callable] = None) -> None:
        self.transitions.setdefault(from_state, {})[event] = (to_state, action)

    def trigger(self, event: str) -> bool:
        if self.state in self.transitions and event in self.transitions[self.state]:
            to_state, action = self.transitions[self.state][event]
            if action:
                action()
            self.state = to_state
            return True
        return False
