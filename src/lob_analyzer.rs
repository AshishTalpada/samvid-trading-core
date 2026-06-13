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

impl Default for LobAnalyzer {
    fn default() -> Self {
        Self::new()
    }
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

        let execs = self.executions_at_level.entry(price_level).or_default();
        execs.push(executed_size);

        // Keep last 10 executions
        if execs.len() > 10 {
            execs.remove(0);
        }

        // If we have at least 4 executions of the EXACT same small size at the same price,
        // it is highly likely an iceberg reloading.
        if execs.len() >= 4 {
            let last_size = execs.last().unwrap();
            let matches = execs
                .iter()
                .filter(|&s| (s - last_size).abs() < 0.001)
                .count();
            if matches >= 4 {
                return true; // Iceberg detected
            }
        }
        false
    }
}

pub fn analyze_iceberg_orders(lob_data: &[u8]) -> bool {
    const HEADER: &[u8; 5] = b"SLOB\x01";
    const RECORD_SIZE: usize = std::mem::size_of::<f64>() * 2;
    let Some(payload) = lob_data.strip_prefix(HEADER) else {
        return false;
    };
    if payload.is_empty() || !payload.len().is_multiple_of(RECORD_SIZE) {
        return false;
    }

    let mut analyzer = LobAnalyzer::new();
    for record in payload.chunks_exact(RECORD_SIZE) {
        let price = f64::from_le_bytes(record[..8].try_into().unwrap());
        let executed_size = f64::from_le_bytes(record[8..].try_into().unwrap());
        if !price.is_finite() || price <= 0.0 || !executed_size.is_finite() || executed_size <= 0.0
        {
            return false;
        }
        if analyzer.detect_iceberg(price, executed_size) {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn execution_bytes(executions: &[(f64, f64)]) -> Vec<u8> {
        let mut payload = b"SLOB\x01".to_vec();
        payload.extend(
            executions.iter().flat_map(|(price, size)| {
                price.to_le_bytes().into_iter().chain(size.to_le_bytes())
            }),
        );
        payload
    }

    #[test]
    fn repeated_same_size_at_same_price_detects_iceberg() {
        let data = execution_bytes(&[
            (100.25, 50.0),
            (100.25, 50.0),
            (100.25, 50.0),
            (100.25, 50.0),
        ]);

        assert!(analyze_iceberg_orders(&data));
    }

    #[test]
    fn arbitrary_large_payload_does_not_trigger() {
        assert!(!analyze_iceberg_orders(&vec![1_u8; 1_024]));
    }

    #[test]
    fn malformed_or_non_finite_records_fail_closed() {
        assert!(!analyze_iceberg_orders(&[0_u8; 15]));
        assert!(!analyze_iceberg_orders(&execution_bytes(&[(
            f64::NAN,
            10.0
        )])));
    }
}
