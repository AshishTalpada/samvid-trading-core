class GameTheoryLogic:
    """Models competitor strategies in illiquid markets."""
    def get_optimal_move(self, my_size: float, competitor_size: float) -> str:
        if my_size > competitor_size * 2:
            return "AGGRESSIVE"
        return "PASSIVE"
