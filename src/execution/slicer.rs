use log::info;
use rand_distr::{Distribution, Normal, Poisson};

/// High-Performance Rust Stealth Slicer
/// Translates the Python slicing logic into microsecond-latency Rust code
/// for the actual FIX engine submission.
pub struct RustStealthSlicer {
    pub base_delay_ms: u64,
    pub noise_scale: f64,
}

impl Default for RustStealthSlicer {
    fn default() -> Self {
        Self::new()
    }
}

impl RustStealthSlicer {
    pub fn new() -> Self {
        RustStealthSlicer {
            base_delay_ms: 100,
            noise_scale: 15.0,
        }
    }

    /// Generates a jittered delay to evade HFT detection algorithms
    pub fn generate_delay(&self) -> u64 {
        let mut rng = rand::thread_rng();

        let base = Poisson::new((self.base_delay_ms as f64).max(f64::EPSILON))
            .map(|distribution| distribution.sample(&mut rng) as f64)
            .unwrap_or(self.base_delay_ms as f64);

        let noise = if self.noise_scale.is_finite() && self.noise_scale > 0.0 {
            Normal::new(0.0, self.noise_scale)
                .map(|distribution| distribution.sample(&mut rng))
                .unwrap_or(0.0)
        } else {
            0.0
        };

        let final_delay = (base + noise).max(5.0) as u64;
        info!("[SLICER-RS] Generated stealth interval: {}ms", final_delay);
        final_delay
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invalid_public_configuration_still_produces_a_safe_delay() {
        let slicer = RustStealthSlicer {
            base_delay_ms: 0,
            noise_scale: f64::NAN,
        };

        assert!(slicer.generate_delay() >= 5);
    }
}
