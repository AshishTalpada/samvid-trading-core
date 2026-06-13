#[cfg(not(test))]
fn global_halt_active() -> bool {
    extern "C" {
        fn is_global_halt_active() -> bool;
    }
    unsafe { is_global_halt_active() }
}

#[cfg(test)]
static TEST_GLOBAL_HALT: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

#[cfg(test)]
fn global_halt_active() -> bool {
    TEST_GLOBAL_HALT.load(std::sync::atomic::Ordering::SeqCst)
}

/// Order Book State for a specific instrument
pub struct InstrumentBook {
    pub best_bid: f64,
    pub best_ask: f64,
    pub bid_size: f64,
    pub ask_size: f64,
    pub exchange_fee_maker: f64,
    pub exchange_fee_taker: f64,
}

pub struct MicroVolArb {
    pub inventory: f64,
    pub max_inventory: f64,
}

impl MicroVolArb {
    pub fn new(max_inventory: f64) -> Self {
        MicroVolArb {
            inventory: 0.0,
            max_inventory: if max_inventory.is_finite() {
                max_inventory.abs()
            } else {
                0.0
            },
        }
    }

    /// High-Frequency Market Making / Micro-Vol Arb logic
    /// Profits from the micro-shivers between bid and ask while earning maker rebates.
    pub fn execute_micro_arb(&mut self, book: &InstrumentBook) -> Option<(f64, f64)> {
        // SAFETY: Check global atomic halt signal before any calculation
        if global_halt_active() {
            return None;
        }

        if self.max_inventory <= 0.0
            || self.inventory.abs() >= self.max_inventory
            || !book.best_bid.is_finite()
            || !book.best_ask.is_finite()
            || !book.exchange_fee_maker.is_finite()
            || book.best_bid <= 0.0
            || book.best_ask <= book.best_bid
            || book.bid_size <= 0.0
            || book.ask_size <= 0.0
        {
            return None;
        }

        let spread = book.best_ask - book.best_bid;

        // Net spread must cover maker fees (often negative, meaning we get paid)
        let min_required_spread = book.best_bid * book.exchange_fee_maker * 2.0;

        if spread > min_required_spread && spread > 0.01 {
            // Arbitrary 1 cent minimum tick
            // We want to provide liquidity on both sides to capture the spread
            let quote_bid = book.best_bid;
            let quote_ask = book.best_ask;

            // Inventory Skewing:
            // If we have too much long inventory, lower our ask to sell faster,
            // and lower our bid to avoid buying more.
            let skew = (self.inventory / self.max_inventory).clamp(-1.0, 1.0);

            let skewed_bid = quote_bid - (skew * spread * 0.5);
            let skewed_ask = quote_ask - (skew * spread * 0.5);

            return Some((skewed_bid, skewed_ask));
        }

        None
    }

    pub fn on_fill(&mut self, side: &str, size: f64) {
        if !size.is_finite() || size <= 0.0 {
            return;
        }
        match side.trim().to_ascii_uppercase().as_str() {
            "BUY" => self.inventory += size,
            "SELL" => self.inventory -= size,
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    static TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn liquid_book() -> InstrumentBook {
        InstrumentBook {
            best_bid: 100.00,
            best_ask: 100.05,
            bid_size: 1_000.0,
            ask_size: 1_000.0,
            exchange_fee_maker: 0.0001,
            exchange_fee_taker: 0.0002,
        }
    }

    #[test]
    fn valid_spread_generates_ordered_quotes() {
        let _guard = TEST_LOCK.lock().unwrap();
        TEST_GLOBAL_HALT.store(false, std::sync::atomic::Ordering::SeqCst);
        let mut arb = MicroVolArb::new(100.0);

        let (bid, ask) = arb.execute_micro_arb(&liquid_book()).unwrap();

        assert!(bid < ask);
        assert_eq!(bid, 100.00);
        assert_eq!(ask, 100.05);
    }

    #[test]
    fn inventory_limit_and_global_halt_block_new_quotes() {
        let _guard = TEST_LOCK.lock().unwrap();
        let mut arb = MicroVolArb::new(100.0);
        arb.inventory = 100.0;
        assert!(arb.execute_micro_arb(&liquid_book()).is_none());

        arb.inventory = 0.0;
        TEST_GLOBAL_HALT.store(true, std::sync::atomic::Ordering::SeqCst);
        assert!(arb.execute_micro_arb(&liquid_book()).is_none());
        TEST_GLOBAL_HALT.store(false, std::sync::atomic::Ordering::SeqCst);
    }

    #[test]
    fn invalid_fill_side_or_size_does_not_corrupt_inventory() {
        let _guard = TEST_LOCK.lock().unwrap();
        let mut arb = MicroVolArb::new(100.0);
        arb.on_fill("BUY", 10.0);
        arb.on_fill("TYPO", 50.0);
        arb.on_fill("SELL", f64::NAN);
        arb.on_fill("SELL", 3.0);

        assert_eq!(arb.inventory, 7.0);
    }
}
