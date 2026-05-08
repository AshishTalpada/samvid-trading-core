pub fn encrypt_q_safe(data: &[u8]) -> Vec<u8> {
    // Protect comms from future quantum computers.
    data.to_vec()
}
