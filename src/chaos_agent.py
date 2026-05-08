import logging
import random
from typing import Dict, List

logger = logging.getLogger(__name__)

class ChaosMonkeyAgent:
    '''
    Intentionally injects faults, drops ticks, and simulates hardware failures
    in the shadow environment to ensure the execution core handles exceptions gracefully.
    '''
    def __init__(self, failure_probability: float = 0.01):
        self.failure_prob = failure_probability
        self.faults_injected = 0

    def intercept_tick(self, tick: Dict[str, float]) -> Dict[str, float]:
        '''Randomly corrupts or drops market data ticks.'''
        if random.random() < self.failure_prob:
            self.faults_injected += 1
            fault_type = random.choice(["DROP", "CORRUPT_PRICE", "CORRUPT_VOLUME", "LATENCY_SPIKE"])

            if fault_type == "DROP":
                logger.warning("[CHAOS] Dropped tick entirely.")
                return {}
            elif fault_type == "CORRUPT_PRICE":
                tick["ask"] *= 10.0 # Flash crash simulation
                logger.warning(f"[CHAOS] Corrupted Ask Price: {tick['ask']}")
            elif fault_type == "LATENCY_SPIKE":
                tick["time_ms"] -= 5000 # Introduce out-of-order 5-second lag
                logger.warning("[CHAOS] Introduced 5s latency spike.")

        return tick

    def intercept_order(self, order: Dict) -> Dict:
        '''Randomly rejects or alters outbound orders.'''
        if random.random() < self.failure_prob:
            self.faults_injected += 1
            logger.warning(f"[CHAOS] Rejected order {order.get('symbol')} at exchange layer.")
            return {"status": "rejected", "message": "Chaos Monkey Exchange Failure"}
        return order
