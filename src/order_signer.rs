use ed25519_dalek::{Signature, Signer, SigningKey};
use log::info;
use rand::rngs::OsRng;

/// Air-Gapped Order Signer (Zero-Trust)
/// Sovereign requires cryptographic signatures for every FIX message
/// sent to institutional brokers. This module mimics an external HSM
/// (Hardware Security Module) that signs the order blob.
pub struct HardwareSigner {
    signing_key: SigningKey,
}

impl HardwareSigner {
    pub fn new() -> Self {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        info!("[SIGNER] Generated Ed25519 air-gapped signing keys.");
        HardwareSigner { signing_key }
    }

    pub fn sign_order(&self, order_blob: &[u8]) -> Signature {
        let signature = self.signing_key.sign(order_blob);
        info!("[SIGNER] Order cryptographically signed.");
        signature
    }
}

impl Default for HardwareSigner {
    fn default() -> Self {
        Self::new()
    }
}
