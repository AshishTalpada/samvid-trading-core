use std::collections::VecDeque;

pub struct TapePrint {
    pub price: f64,
    pub volume: u64,
    pub exchange_code: String, // E.g., "FINRA ADF" for dark pools
    pub condition_flags: u32,
}

pub struct DarkPoolDetector {
    pub recent_tape: VecDeque<TapePrint>,
    pub adf_total_volume: u64,
    pub lit_total_volume: u64,
}

impl DarkPoolDetector {
    pub fn new() -> Self {
        DarkPoolDetector {
            recent_tape: VecDeque::with_capacity(10000),
            adf_total_volume: 0,
            lit_total_volume: 0,
        }
    }

    /// Process a Time and Sales tape print.
    /// Returns true if a massive Dark Pool block is detected.
    pub fn detect_dark_pool_block(&mut self, print: TapePrint) -> bool {
        let is_dark = print.exchange_code.contains("ADF") || print.exchange_code == "D";
        
        if is_dark {
            self.adf_total_volume += print.volume;
        } else {
            self.lit_total_volume += print.volume;
        }

        self.recent_tape.push_back(print);
        if self.recent_tape.len() > 10000 {
            if let Some(old) = self.recent_tape.pop_front() {
                if old.exchange_code.contains("ADF") || old.exchange_code == "D" {
                    self.adf_total_volume -= old.volume;
                } else {
                    self.lit_total_volume -= old.volume;
                }
            }
        }

        // True block trade condition:
        // Single dark print > 50,000 shares OR
        // Dark pool volume in the last 10,000 prints exceeds 60% of total volume
        if is_dark && print.volume > 50_000 {
            return true;
        }
        
        let total_vol = self.adf_total_volume + self.lit_total_volume;
        if total_vol > 0 && (self.adf_total_volume as f64 / total_vol as f64) > 0.60 {
            return true;
        }

        false
    }
}
