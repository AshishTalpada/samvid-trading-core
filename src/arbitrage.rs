use std::collections::HashMap;

/// Directed Edge for Triangular/Cross-Exchange Arbitrage Graph
#[derive(Debug, Clone)]
pub struct ArbEdge {
    pub from_asset: String,
    pub to_asset: String,
    pub exchange: String,
    pub rate: f64,          // Exchange rate
    pub fee: f64,           // Transaction fee percentage (0.001 = 0.1%)
    pub capacity: f64,      // Maximum size available at this rate
}

pub struct ArbGraph {
    pub edges: Vec<ArbEdge>,
}

impl ArbGraph {
    pub fn new() -> Self {
        ArbGraph { edges: Vec::new() }
    }

    pub fn update_edge(&mut self, edge: ArbEdge) {
        // Overwrite existing edge or push new
        if let Some(e) = self.edges.iter_mut().find(|e| e.from_asset == edge.from_asset && e.to_asset == edge.to_asset && e.exchange == edge.exchange) {
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
            if !nodes.contains(&e.from_asset) { nodes.push(e.from_asset.clone()); }
            if !nodes.contains(&e.to_asset) { nodes.push(e.to_asset.clone()); }
            distances.insert(e.from_asset.clone(), std::f64::INFINITY);
            distances.insert(e.to_asset.clone(), std::f64::INFINITY);
        }

        distances.insert(start_node.to_string(), 0.0);

        // Relax edges |V| - 1 times
        let v_count = nodes.len();
        for _ in 0..v_count - 1 {
            for e in &self.edges {
                let u_dist = *distances.get(&e.from_asset).unwrap_or(&std::f64::INFINITY);
                let net_rate = e.rate * (1.0 - e.fee);
                let weight = -net_rate.ln(); // Negative log weight
                
                if u_dist != std::f64::INFINITY && u_dist + weight < *distances.get(&e.to_asset).unwrap() {
                    distances.insert(e.to_asset.clone(), u_dist + weight);
                    predecessors.insert(e.to_asset.clone(), e.clone());
                }
            }
        }

        // Check for negative weight cycle (arbitrage loop)
        for e in &self.edges {
            let u_dist = *distances.get(&e.from_asset).unwrap_or(&std::f64::INFINITY);
            let net_rate = e.rate * (1.0 - e.fee);
            let weight = -net_rate.ln();
            
            if u_dist != std::f64::INFINITY && u_dist + weight < *distances.get(&e.to_asset).unwrap() {
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
