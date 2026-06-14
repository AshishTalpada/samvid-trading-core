import logging
from typing import Any, Callable, List

logger = logging.getLogger(__name__)


class CategoryTheoryVerifier:
    """
    Applies Category Theory (functors and natural transformations) to verify
    that reasoning chains are internally consistent and composable.
    A valid trade hypothesis must form a commutative diagram:
    Signal → Risk-Check → Size → Entry must compose cleanly without contradiction.
    """

    def __init__(self):
        self._morphisms: List[tuple[str, Callable]] = []

    def add_morphism(self, name: str, fn: Callable[[Any], Any]) -> None:
        self._morphisms.append((name, fn))

    def compose(self, initial_value: Any) -> tuple[Any, bool]:
        current = initial_value
        for name, fn in self._morphisms:
            try:
                current = fn(current)
                if current is None:
                    logger.error(f"[CAT THEORY] Morphism '{name}' returned None. Functor broken.")
                    return None, False
            except Exception as e:
                logger.error(f"[CAT THEORY] Morphism '{name}' failed: {e}")
                return None, False
        return current, True

    def verify_commutativity(
        self, path_a: List[Callable], path_b: List[Callable], input_val: Any
    ) -> bool:
        # Compose path_a
        result_a: Any = input_val
        ok_a = True
        for i, fn in enumerate(path_a):
            try:
                result_a = fn(result_a)
                if result_a is None:
                    logger.error(f"[CAT THEORY] path_a step {i} returned None. Functor broken.")
                    ok_a = False
                    break
            except Exception as e:
                logger.error(f"[CAT THEORY] path_a step {i} failed: {e}")
                ok_a = False
                break

        # Compose path_b
        result_b: Any = input_val
        ok_b = True
        for i, fn in enumerate(path_b):
            try:
                result_b = fn(result_b)
                if result_b is None:
                    ok_b = False
                    break
            except Exception as e:
                logger.error(f"[CAT THEORY] path_b step {i} failed: {e}")
                ok_b = False
                break

        if not ok_a or not ok_b:
            logger.info("[CAT THEORY] Commutativity: FAIL (composition error)")
            return False
        equal = result_a == result_b
        logger.info(f"[CAT THEORY] Commutativity: {'PASS' if equal else 'FAIL'}")
        return bool(equal)
