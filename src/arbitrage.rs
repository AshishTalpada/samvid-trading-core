use std::collections::HashMap;

/// Directed Edge for Triangular/Cross-Exchange Arbitrage Graph
#[derive(Debug, Clone)]
pub struct ArbEdge {
    pub from_asset: String,
    pub to_asset: String,
    pub exchange: String,
    pub rate: f64,     // Exchange rate
    pub fee: f64,      // Transaction fee percentage (0.001 = 0.1%)
    pub capacity: f64, // Maximum size available at this rate
}

pub struct ArbGraph {
    pub edges: Vec<ArbEdge>,
}

impl Default for ArbGraph {
    fn default() -> Self {
        Self::new()
    }
}

impl ArbGraph {
    pub fn new() -> Self {
        ArbGraph { edges: Vec::new() }
    }

    pub fn update_edge(&mut self, edge: ArbEdge) {
        // Overwrite existing edge or push new
        if let Some(e) = self.edges.iter_mut().find(|e| {
            e.from_asset == edge.from_asset
                && e.to_asset == edge.to_asset
                && e.exchange == edge.exchange
        }) {
            *e = edge;
        } else {
            self.edges.push(edge);
        }
    }

    /// Bellman-Ford algorithm to detect Negative Cycles (Arbitrage Opportunities)
    /// We use negative log of the rate to convert multiplication to addition.
    pub fn detect_cross_exchange_arb(&self, start_node: &str) -> Option<Vec<ArbEdge>> {
        let mut distances: HashMap<String, f64> = HashMap::new();
        let mut predecessors: HashMap<String, ArbEdge> = HashMap::new();
        let mut nodes = Vec::new();

        for e in &self.edges {
            if !nodes.contains(&e.from_asset) {
                nodes.push(e.from_asset.clone());
            }
            if !nodes.contains(&e.to_asset) {
                nodes.push(e.to_asset.clone());
            }
            distances.insert(e.from_asset.clone(), f64::INFINITY);
            distances.insert(e.to_asset.clone(), f64::INFINITY);
        }

        distances.insert(start_node.to_string(), 0.0);

        // Relax edges |V| - 1 times
        let v_count = nodes.len();
        for _ in 0..v_count.saturating_sub(1) {
            for e in &self.edges {
                let u_dist = *distances.get(&e.from_asset).unwrap_or(&f64::INFINITY);
                let net_rate = e.rate * (1.0 - e.fee);
                if net_rate <= 0.0 {
                    continue;
                } // Avoid log of 0 or negative
                let weight = -net_rate.ln(); // Negative log weight

                if u_dist != f64::INFINITY
                    && u_dist + weight < *distances.get(&e.to_asset).unwrap_or(&f64::INFINITY)
                {
                    distances.insert(e.to_asset.clone(), u_dist + weight);
                    predecessors.insert(e.to_asset.clone(), e.clone());
                }
            }
        }

        // Check for negative weight cycle (arbitrage loop)
        for e in &self.edges {
            let u_dist = *distances.get(&e.from_asset).unwrap_or(&f64::INFINITY);
            let net_rate = e.rate * (1.0 - e.fee);
            if net_rate <= 0.0 {
                continue;
            }
            let weight = -net_rate.ln();

            if u_dist != f64::INFINITY
                && u_dist + weight < *distances.get(&e.to_asset).unwrap_or(&f64::INFINITY)
            {
                // Negative cycle found. Trace back to get the cycle path.
                let mut cycle = Vec::new();
                let mut curr = e.from_asset.clone();
                let mut visited = Vec::new();

                while let Some(pred_edge) = predecessors.get(&curr) {
                    if visited.contains(&curr) {
                        break; // Loop closed
                    }
                    visited.push(curr.clone());
                    cycle.push(pred_edge.clone());
                    curr = pred_edge.from_asset.clone();
                }
                cycle.reverse();
                return Some(cycle);
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn edge(from: &str, to: &str, rate: f64) -> ArbEdge {
        ArbEdge {
            from_asset: from.to_string(),
            to_asset: to.to_string(),
            exchange: "TEST".to_string(),
            rate,
            fee: 0.0,
            capacity: 1_000.0,
        }
    }

    #[test]
    fn empty_graph_has_no_arbitrage() {
        let graph = ArbGraph::new();

        assert!(graph.detect_cross_exchange_arb("USD").is_none());
    }

    #[test]
    fn profitable_cycle_is_detected() {
        let mut graph = ArbGraph::new();
        graph.update_edge(edge("USD", "EUR", 0.90));
        graph.update_edge(edge("EUR", "GBP", 0.90));
        graph.update_edge(edge("GBP", "USD", 1.30));

        let cycle = graph.detect_cross_exchange_arb("USD");

        assert!(cycle.is_some());
        assert!(!cycle.unwrap().is_empty());
    }

    #[test]
    fn edge_updates_replace_the_same_market() {
        let mut graph = ArbGraph::new();
        graph.update_edge(edge("USD", "EUR", 0.90));
        graph.update_edge(edge("USD", "EUR", 0.95));

        assert_eq!(graph.edges.len(), 1);
        assert_eq!(graph.edges[0].rate, 0.95);
    }
}
