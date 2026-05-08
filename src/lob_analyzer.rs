use std::collections::HashMap;

/// Represents a single order in the Level 3 Order Book.
#[derive(Debug, Clone)]
pub struct L3Order {
    pub order_id: u64,
    pub price: f64,
    pub size: f64,
    pub is_bid: bool,
    pub timestamp_ns: u64,
}

/// State tracking for Iceberg detection
pub struct LobAnalyzer {
    pub order_history: HashMap<u64, L3Order>,
    pub executions_at_level: HashMap<i64, Vec<f64>>, // Price (scaled) -> Vec of executed sizes
}

impl LobAnalyzer {
    pub fn new() -> Self {
        LobAnalyzer {
            order_history: HashMap::new(),
            executions_at_level: HashMap::new(),
        }
    }

    /// Process incoming order.
    pub fn on_order_added(&mut self, order: L3Order) {
        self.order_history.insert(order.order_id, order);
    }

    /// Analyze if a level has repeating identical small executions (Iceberg signature).
    pub fn detect_iceberg(&mut self, price: f64, executed_size: f64) -> bool {
        let price_level = (price * 10000.0) as i64; // Scale to int for hashing
        
        let execs = self.executions_at_level.entry(price_level).or_insert(Vec::new());
        execs.push(executed_size);

        // Keep last 10 executions
        if execs.len() > 10 {
            execs.remove(0);
        }

        // If we have at least 4 executions of the EXACT same small size at the same price,
        // it is highly likely an iceberg reloading.
        if execs.len() >= 4 {
            let last_size = execs.last().unwrap();
            let matches = execs.iter().filter(|&s| (s - last_size).abs() < 0.001).count();
            if matches >= 4 {
                return true; // Iceberg detected
            }
        }
        false
    }
}

pub fn analyze_iceberg_orders(lob_data: &[u8]) -> bool {
    // Stub for C FFI wrapper entry point.
    // In production, this parses binary ITCH protocol and calls the LobAnalyzer.
    lob_data.len() > 1000
}
