pub fn detect_cross_exchange_arb(price_a: f64, price_b: f64) -> f64 {
    // Spot the same stock at different prices on ECNs
    (price_a - price_b).abs()
}
