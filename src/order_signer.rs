use ed25519_dalek::{Keypair, Signer, Signature};
use rand::rngs::OsRng;
use log::info;

/// Air-Gapped Order Signer (Zero-Trust)
/// Sovereign requires cryptographic signatures for every FIX message
/// sent to institutional brokers. This module mimics an external HSM
/// (Hardware Security Module) that signs the order blob.

pub struct HardwareSigner {
    keypair: Keypair,
}

impl HardwareSigner {
    pub fn new() -> Self {
        let mut csprng = OsRng{};
        let keypair = Keypair::generate(&mut csprng);
        info!("[SIGNER] Generated Ed25519 air-gapped signing keys.");
        HardwareSigner { keypair }
    }

    pub fn sign_order(&self, order_blob: &[u8]) -> Signature {
        let signature = self.keypair.sign(order_blob);
        info!("[SIGNER] Order cryptographically signed.");
        signature
    }
}
