pub struct ItchMessage {
    pub msg_type: u8,
    pub order_ref: u64,
}

pub fn parse_itch(data: &[u8]) -> ItchMessage {
    // Direct binary parsing
    ItchMessage {
        msg_type: data[0],
        order_ref: u64::from_be_bytes(data[1..9].try_into().unwrap()),
    }
}
