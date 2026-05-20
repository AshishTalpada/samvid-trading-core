use std::{mem, ptr};

#[derive(Debug, Clone, Copy)]
#[repr(C, packed)]
pub struct ItchMessageHeader {
    pub msg_type: u8,
    pub stock_locate: u16,
    pub tracking_number: u16,
    pub timestamp: u64,
}

#[derive(Debug, Clone, Copy)]
#[repr(C, packed)]
pub struct AddOrderMessage {
    pub header: ItchMessageHeader,
    pub order_ref: u64,
    pub buy_sell: u8,
    pub shares: u32,
    pub stock: [u8; 8],
    pub price: u32,
}

/// ITCH 5.0 message parser.
/// Copies one packed message with `read_unaligned` so packet buffers do not
/// need to satisfy Rust reference alignment guarantees.
#[inline(always)]
pub fn parse_itch_zero_copy(data: &[u8]) -> Option<AddOrderMessage> {
    if data.len() < mem::size_of::<AddOrderMessage>() {
        return None;
    }
    // SAFETY: We checked the length above. `read_unaligned` avoids creating an
    // invalid reference to a packed/alignment-unknown network buffer.
    let msg = unsafe { ptr::read_unaligned(data.as_ptr() as *const AddOrderMessage) };
    Some(msg)
}
