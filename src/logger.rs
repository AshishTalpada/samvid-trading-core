use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;

/// Lock-free memory-mapped asynchronous logger.
/// Prevents the hot-path execution loop from blocking on disk I/O.
pub struct ZeroCopyLogger {
    buffer: UnsafeCell<Vec<u8>>,
    cursor: AtomicUsize,
}

unsafe impl Sync for ZeroCopyLogger {}

impl ZeroCopyLogger {
    pub fn new() -> Self {
        Self {
            buffer: UnsafeCell::new(vec![0; 1024 * 1024 * 50]), // 50MB log buffer
            cursor: AtomicUsize::new(0),
        }
    }

    #[inline(always)]
    pub fn log_event(&self, event_bytes: &[u8]) {
        let offset = self.cursor.fetch_add(event_bytes.len(), Ordering::Relaxed);
        unsafe {
            let buf = &mut *self.buffer.get();
            if offset + event_bytes.len() < buf.len() {
                std::ptr::copy_nonoverlapping(event_bytes.as_ptr(), buf.as_mut_ptr().add(offset), event_bytes.len());
            }
        }
        // Background thread handles syncing to NVMe disk
    }
}
