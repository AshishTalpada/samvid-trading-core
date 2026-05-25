import logging

import numpy as np

logger = logging.getLogger(__name__)


class GNNSentimentAgent:
    """
    Graph Neural Network (GNN) implementation for Sentiment Ripple tracking.
    Simulates how information propagates through a network of correlated entities.
    """

    def __init__(self, num_nodes: int = 100):
        self.num_nodes = num_nodes
        # Adjacency matrix representing edge weights (correlations) between entities
        self.adj_matrix = np.random.uniform(0, 0.1, (num_nodes, num_nodes))
        np.fill_diagonal(self.adj_matrix, 1.0)
        # Node features: [sentiment_score, volume_spike, media_mentions]
        self.node_features = np.zeros((num_nodes, 3))
        # GNN weights for message passing
        self.W = np.random.randn(3, 3) * 0.01

    def track_ripple(self, source_node: int, sentiment_shock: float) -> np.ndarray:
        """
        Injects a sentiment shock at a source node and propagates it using Graph Convolution.
        Returns the updated sentiment scores for all nodes.
        """
        if source_node >= self.num_nodes:
            logger.error("Source node out of bounds")
            return np.zeros(self.num_nodes)

        # Inject shock
        self.node_features[source_node, 0] += sentiment_shock

        # Graph Convolution Layer: H^{(l+1)} = \sigma(A * H^{(l)} * W)
        # 1. Aggregate neighborhood features
        aggregated_features = np.dot(self.adj_matrix, self.node_features)

        # 2. Linear transformation via weight matrix W
        transformed = np.dot(aggregated_features, self.W)

        # 3. Non-linear activation (Tanh to keep sentiment between -1 and 1)
        updated_features = np.tanh(transformed)

        self.node_features = updated_features
        return self.node_features[:, 0]  # Return the primary sentiment dimension
