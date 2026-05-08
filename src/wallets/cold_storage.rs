pub fn sync_cold_wallet(amount: f64) -> bool {
    // Move trading profits to an offline cold wallet
    if amount > 10000.0 {
        return true;
    }
    false
}
