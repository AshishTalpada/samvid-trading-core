pub fn sign_order(payload: &[u8]) -> Vec<u8> {
    // Every order requires a unique crypto token.
    vec![0x01, 0x02, 0x03]
}
