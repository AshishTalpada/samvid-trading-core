class DrawdownDuration:
    """Predicting how long a losing streak will last."""
    def __init__(self, average_win_rate: float):
        self.win_rate = average_win_rate

    def probability_of_streak(self, length: int) -> float:
        # P(Losing Streak of length N) = (1 - win_rate)^N
        loss_rate = 1.0 - self.win_rate
        return loss_rate ** length
