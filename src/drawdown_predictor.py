import logging

import numpy as np

logger = logging.getLogger(__name__)


class DrawdownPredictor:
    """
    Models drawdowns using a Markov Chain to predict psychological pain duration.
    States: 0 (Winning), 1 (Small Loss), 2 (Deep Drawdown)
    """

    def __init__(self):
        # Transition matrix P[i, j] = probability of moving from state i to state j
        # Assumes autocorrelation in losses (losses cluster together)
        self.transition_matrix = np.array(
            [
                [0.60, 0.30, 0.10],  # From Winning
                [0.40, 0.40, 0.20],  # From Small Loss
                [0.20, 0.30, 0.50],  # From Deep Drawdown (hard to escape)
            ]
        )

    def predict_duration(self, current_state: int, target_state: int = 0) -> float:
        """
        Calculates the Expected Hitting Time (Fundamental Matrix) from current_state to target_state.
        Returns the expected number of trades/days required to escape the drawdown.
        """
        if current_state == target_state:
            return 0.0

        n = self.transition_matrix.shape[0]

        # Remove the target state row and column to create matrix Q
        states_to_keep = [i for i in range(n) if i != target_state]
        Q = self.transition_matrix[np.ix_(states_to_keep, states_to_keep)]

        # Fundamental matrix N = (I - Q)^-1
        I = np.eye(len(states_to_keep))
        try:
            N = np.linalg.inv(I - Q)
            # Expected times to absorption are the row sums of N
            expected_times = np.sum(N, axis=1)

            # Map current_state to its index in the reduced matrix
            idx = states_to_keep.index(current_state)
            return float(expected_times[idx])
        except np.linalg.LinAlgError:
            logger.error("Singular matrix in Markov calculation.")
            return -1.0
