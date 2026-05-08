use std::arch::x86_64::_rdtsc;

pub fn randomize_sleep_cycles() {
    unsafe {
        let tsc = _rdtsc();
        let jitter = tsc % 1000;
        // Inject random nop sled to defeat power-analysis side channels
        for _ in 0..jitter {
            std::arch::asm!("nop");
        }
    }
}
