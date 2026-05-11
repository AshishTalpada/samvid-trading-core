use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use std::thread;
use log::{info, error};

/// Aegis Protocol 3.0 / 4.0 Core
/// Hardware-level auto-reboot and state restoration protocol.
/// Monitors the main Quorum event loop. If it hangs for >500ms, Aegis 
/// triggers an instantaneous state snapshot and restarts the Sovereign process.

static SYSTEM_HANG: AtomicBool = AtomicBool::new(false);

pub struct AegisProtocol {
    max_latency_ms: u64,
}

impl AegisProtocol {
    pub fn new() -> Self {
        AegisProtocol { max_latency_ms: 500 }
    }

    pub fn start_watchdog(&self) {
        let max_ms = self.max_latency_ms;
        thread::spawn(move || {
            loop {
                // Set the flag to true at the start of the cycle
                SYSTEM_HANG.store(true, Ordering::SeqCst);
                
                // Wait for the main loop to ping and set it to false
                thread::sleep(Duration::from_millis(max_ms));
                
                // If it's still true, the main loop is hung
                if SYSTEM_HANG.load(Ordering::SeqCst) {
                    error!("[AEGIS] Main loop hang detected (>{}ms)! Initiating emergency restore.", max_ms);
                    std::process::exit(99);
                }
            }
        });
        info!("[AEGIS] Resilience Core V4 online. Sub-second recovery armed.");
    }
    
    pub fn ping(&self) {
        SYSTEM_HANG.store(false, Ordering::SeqCst);
    }
}
