use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;

extern "C" {
    fn is_global_halt_active() -> bool;
}

const QUEUE_SIZE: usize = 1024 * 1024; // 1M events

/// Wait-free, zero-copy SPSC (Single Producer, Single Consumer) Ring Buffer
/// Bypasses OS locks completely for cross-thread orchestrator coordination.
pub struct ZeroCopyQueue {
    buffer: UnsafeCell<Vec<u8>>,
    head: AtomicUsize,
    tail: AtomicUsize,
}

unsafe impl Sync for ZeroCopyQueue {}

impl ZeroCopyQueue {
    pub fn new() -> Self {
        Self {
            buffer: UnsafeCell::new(vec![0; QUEUE_SIZE]),
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
        }
    }

    #[inline(always)]
    pub fn push(&self, data: &[u8]) -> Result<(), &str> {
        if unsafe { is_global_halt_active() } {
            return Err("System Halted");
        }
        
        let current_tail = self.tail.load(Ordering::Relaxed);
        let current_head = self.head.load(Ordering::Acquire);
        
        if current_tail.wrapping_add(data.len()) - current_head > QUEUE_SIZE {
            return Err("Queue Full");
        }
        
        unsafe {
            let buf = &mut *self.buffer.get();
            let start = current_tail % QUEUE_SIZE;
            
            if start + data.len() <= QUEUE_SIZE {
                std::ptr::copy_nonoverlapping(data.as_ptr(), buf.as_mut_ptr().add(start), data.len());
            } else {
                let chunk1 = QUEUE_SIZE - start;
                std::ptr::copy_nonoverlapping(data.as_ptr(), buf.as_mut_ptr().add(start), chunk1);
                std::ptr::copy_nonoverlapping(data.as_ptr().add(chunk1), buf.as_mut_ptr(), data.len() - chunk1);
            }
        }
        
        self.tail.store(current_tail.wrapping_add(data.len()), Ordering::Release);
        Ok(())
    }
}
