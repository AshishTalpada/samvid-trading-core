/// Deep Dive: Constant-Time Execution to prevent Power/Timing Side-Channel attacks.
pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut result: u8 = 0;
    // Iterate over the ENTIRE slice regardless of matches to prevent timing attacks.
    for i in 0..a.len() {
        result |= a[i] ^ b[i];
    }
    result == 0
}

pub fn mask_private_key(key: &mut [u8], random_mask: &[u8]) {
    // Blinding operation to obfuscate power draw during key signing
    for i in 0..key.len() {
        key[i] ^= random_mask[i % random_mask.len()];
    }
}
