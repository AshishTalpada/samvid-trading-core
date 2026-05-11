use std::cmp::Ordering;
extern "C" {
    fn is_global_halt_active() -> bool;
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
            max_inventory,
        }
    }

    /// High-Frequency Market Making / Micro-Vol Arb logic
    /// Profits from the micro-shivers between bid and ask while earning maker rebates.
    pub fn execute_micro_arb(&mut self, book: &InstrumentBook) -> Option<(f64, f64)> {
        // SAFETY: Check global atomic halt signal before any calculation
        if unsafe { is_global_halt_active() } {
            return None; 
        }

        let spread = book.best_ask - book.best_bid;
        
        // Net spread must cover maker fees (often negative, meaning we get paid)
        let min_required_spread = book.best_bid * book.exchange_fee_maker * 2.0;
        
        if spread > min_required_spread && spread > 0.01 { // Arbitrary 1 cent minimum tick
            // We want to provide liquidity on both sides to capture the spread
            let quote_bid = book.best_bid;
            let quote_ask = book.best_ask;
            
            // Inventory Skewing:
            // If we have too much long inventory, lower our ask to sell faster,
            // and lower our bid to avoid buying more.
            let skew = if self.max_inventory > 0.0 {
                self.inventory / self.max_inventory
            } else {
                0.0
            };
            
            let skewed_bid = quote_bid - (skew * spread * 0.5);
            let skewed_ask = quote_ask - (skew * spread * 0.5);
            
            return Some((skewed_bid, skewed_ask));
        }
        
        None
    }

    pub fn on_fill(&mut self, side: &str, size: f64) {
        if side == "BUY" {
            self.inventory += size;
        } else {
            self.inventory -= size;
        }
    }
}
