use std::mem;

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

/// Zero-copy ITCH 5.0 message parser
/// Casts raw UDP network bytes directly to struct memory representation
/// avoiding all serialization/deserialization latency.
#[inline(always)]
pub fn parse_itch_zero_copy(data: &[u8]) -> Option<&AddOrderMessage> {
    if data.len() < mem::size_of::<AddOrderMessage>() {
        return None;
    }
    // SAFETY: Input slice is guaranteed to be large enough, 
    // and network buffers are guaranteed aligned by the kernel-bypass NIC.
    let msg = unsafe { &*(data.as_ptr() as *const AddOrderMessage) };
    Some(msg)
}
