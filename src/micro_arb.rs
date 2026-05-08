pub fn execute_micro_arb(bid: f64, ask: f64) -> f64 {
    // Profit from tiny shivers between bid/ask
    if ask - bid > 0.01 {
        return ask - bid;
    }
    0.0
}
