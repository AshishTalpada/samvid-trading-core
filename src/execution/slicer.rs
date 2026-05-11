use rand_distr::{Poisson, Normal, Distribution};
use log::info;

/// High-Performance Rust Stealth Slicer
/// Translates the Python slicing logic into microsecond-latency Rust code
/// for the actual FIX engine submission.
pub struct RustStealthSlicer {
    pub base_delay_ms: u64,
    pub noise_scale: f64,
}

impl RustStealthSlicer {
    pub fn new() -> Self {
        RustStealthSlicer { base_delay_ms: 100, noise_scale: 15.0 }
    }

    /// Generates a jittered delay to evade HFT detection algorithms
    pub fn generate_delay(&self) -> u64 {
        let mut rng = rand::thread_rng();
        
        let poi = Poisson::new(self.base_delay_ms as f64).unwrap();
        let base = poi.sample(&mut rng) as f64;
        
        let normal = Normal::new(0.0, self.noise_scale).unwrap();
        let noise = normal.sample(&mut rng);
        
        let final_delay = (base + noise).max(5.0) as u64;
        info!("[SLICER-RS] Generated stealth interval: {}ms", final_delay);
        final_delay
    }
}
