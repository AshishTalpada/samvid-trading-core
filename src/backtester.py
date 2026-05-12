import numpy as np
import logging
from mind_experiment import MindExperiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class WalkForwardBacktester:
    """
    Phase 4: Institutional-grade Walk-Forward Validation.
    This backtester rigorously tests the Autonomous Neuro-Evolution to ensure
    the genetic algorithm is actually finding signal, rather than just over-fitting
    to historical noise.
    """
    def __init__(self, experiment: MindExperiment):
        self.experiment = experiment

    def run_walk_forward(self, data_series: np.ndarray, labels: np.ndarray, train_window: int, test_window: int, generations: int = 50):
        """
        Runs a rolling Walk-Forward Analysis (e.g. Train on 2 years, Test on 1 year, roll forward).
        """
        total_length = data_series.shape[0]
        logger.info(f"Starting Walk-Forward Analysis on {total_length} periods.")
        
        # Initialize an arbitrary starting "brain" weight
        base_weights = np.random.randn(data_series.shape[1])
        
        test_pnl = []
        
        for start_idx in range(0, total_length - train_window - test_window + 1, test_window):
            train_end = start_idx + train_window
            test_end = train_end + test_window
            
            train_data = data_series[start_idx:train_end]
            train_labels = labels[start_idx:train_end]
            
            test_data = data_series[train_end:test_end]
            test_labels = labels[train_end:test_end]
            
            logger.info(f"--- Walk-Forward Window [{start_idx}:{train_end}] (Train) -> [{train_end}:{test_end}] (Test) ---")
            
            # 1. Train Phase (Neuro-Evolution)
            self.experiment.init_population(base_weights)
            apex_weights = base_weights
            
            for gen in range(generations):
                self.experiment.evaluate_fitness(train_data, train_labels)
                apex_weights = self.experiment.breed_next_generation()
                
            # 2. Test Phase (Out-of-Sample)
            # Simplified PnL proxy: dot product represents position sizing (-1 to 1)
            # Multiplied by actual label (next period return)
            predictions = np.dot(test_data, apex_weights)
            
            # Simple thresholding: go long if > 0, short if < 0
            positions = np.sign(predictions)
            window_pnl = np.sum(positions * test_labels)
            
            test_pnl.append(window_pnl)
            logger.info(f"Out-of-Sample PnL for window: {window_pnl:.4f}")
            
            # Roll forward: The new base_weights for the next training window are the apex weights from this one
            base_weights = apex_weights
            
        total_oos_pnl = np.sum(test_pnl)
        logger.info(f"=== Walk-Forward Analysis Complete ===")
        logger.info(f"Total Out-Of-Sample PnL: {total_oos_pnl:.4f}")
        return test_pnl

if __name__ == "__main__":
    # Mock integration test
    logger.info("Initializing Walk-Forward Backtester with simulated market data...")
    
    # Simulate 10 years of daily data (2520 trading days) across 10 features
    sim_data = np.random.randn(2520, 10)
    # Simulate next-day returns (with a tiny embedded linear signal for the GA to find)
    hidden_signal = np.random.randn(10)
    sim_labels = np.dot(sim_data, hidden_signal) * 0.05 + np.random.randn(2520) * 0.1
    
    # Mock Bridge
    class MockBridge:
        def register_tool(self, *args): pass
        
    exp = MindExperiment(MockBridge())
    backtester = WalkForwardBacktester(exp)
    
    # Train on 500 days, test on 250 days
    backtester.run_walk_forward(sim_data, sim_labels, train_window=500, test_window=250, generations=20)
