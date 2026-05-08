use std::sync::atomic::{AtomicUsize, Ordering};

pub struct ZeroCopyQueue {
    buffer: *mut u8,
    head: AtomicUsize,
    tail: AtomicUsize,
}

impl ZeroCopyQueue {
    pub fn push(&self, data: &[u8]) {
        // Zero-copy mem push
        self.head.fetch_add(data.len(), Ordering::SeqCst);
    }
}
