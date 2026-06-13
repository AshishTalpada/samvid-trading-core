use std::collections::VecDeque;

const LARGE_BLOCK_SHARES: u64 = 50_000;
const MIN_RATIO_SAMPLE_VOLUME: u64 = 100_000;
const DARK_VOLUME_RATIO_THRESHOLD: f64 = 0.60;

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

impl Default for DarkPoolDetector {
    fn default() -> Self {
        Self::new()
    }
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
            self.adf_total_volume = self.adf_total_volume.saturating_add(print.volume);
        } else {
            self.lit_total_volume = self.lit_total_volume.saturating_add(print.volume);
        }

        // True block trade condition:
        // Single dark print > 50,000 shares
        let is_large_block = is_dark && print.volume > LARGE_BLOCK_SHARES;

        self.recent_tape.push_back(print);
        if self.recent_tape.len() > 10000 {
            if let Some(old) = self.recent_tape.pop_front() {
                if old.exchange_code.contains("ADF") || old.exchange_code == "D" {
                    self.adf_total_volume = self.adf_total_volume.saturating_sub(old.volume);
                } else {
                    self.lit_total_volume = self.lit_total_volume.saturating_sub(old.volume);
                }
            }
        }

        if is_large_block {
            return true;
        }

        let total_vol = self.adf_total_volume + self.lit_total_volume;
        if total_vol >= MIN_RATIO_SAMPLE_VOLUME
            && (self.adf_total_volume as f64 / total_vol as f64) > DARK_VOLUME_RATIO_THRESHOLD
        {
            return true;
        }

        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn print(exchange_code: &str, volume: u64) -> TapePrint {
        TapePrint {
            price: 100.0,
            volume,
            exchange_code: exchange_code.to_string(),
            condition_flags: 0,
        }
    }

    #[test]
    fn small_dark_print_does_not_trigger_on_an_empty_sample() {
        let mut detector = DarkPoolDetector::new();

        assert!(!detector.detect_dark_pool_block(print("ADF", 100)));
    }

    #[test]
    fn large_dark_block_triggers_immediately() {
        let mut detector = DarkPoolDetector::new();

        assert!(detector.detect_dark_pool_block(print("D", 50_001)));
    }

    #[test]
    fn dark_ratio_requires_meaningful_total_volume() {
        let mut detector = DarkPoolDetector::new();
        assert!(!detector.detect_dark_pool_block(print("ADF", 20_000)));
        assert!(!detector.detect_dark_pool_block(print("ADF", 20_000)));
        assert!(!detector.detect_dark_pool_block(print("NYSE", 20_000)));
        assert!(!detector.detect_dark_pool_block(print("NYSE", 20_000)));
        assert!(!detector.detect_dark_pool_block(print("ADF", 20_000)));

        assert!(detector.detect_dark_pool_block(print("ADF", 1_000)));
    }
}
