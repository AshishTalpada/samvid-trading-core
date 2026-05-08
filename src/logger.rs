use std::sync::atomic::{AtomicUsize, Ordering};
use std::ptr;

pub struct LockFreeRingBuffer {
    buffer: *mut u8,
    capacity: usize,
    head: AtomicUsize,
    tail: AtomicUsize,
}

impl LockFreeRingBuffer {
    pub fn write_log(&self, msg: &[u8]) {
        let current_tail = self.tail.fetch_add(msg.len(), Ordering::Relaxed);
        // Direct pointer arithmetic for zero-pause logging
        unsafe {
            ptr::copy_nonoverlapping(msg.as_ptr(), self.buffer.add(current_tail % self.capacity), msg.len());
        }
    }
}
