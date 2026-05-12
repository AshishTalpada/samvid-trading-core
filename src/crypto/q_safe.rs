// =========================================================================
// DEPRECATION WARNING: Phase 2 De-bloat
// Using pqcrypto_kyber for internal application channels adds unnecessary 
// CPU overhead. Use standard Unix Domain Sockets or TLS 1.3.
// =========================================================================
#![cfg(feature = "experimental_crypto")]

use pqcrypto_kyber::kyber1024;
use pqcrypto_kyber::kyber1024::{Ciphertext, PublicKey, SecretKey, SharedSecret};
use log::info;

/// Post-Quantum Cryptography Module (Kyber-1024)
/// Secures the Sovereign architecture against future quantum decryption attacks.
pub struct QuantumSafeChannel {
    pub public_key: PublicKey,
    secret_key: SecretKey,
}

impl QuantumSafeChannel {
    pub fn new() -> Self {
        let (pk, sk) = kyber1024::keypair();
        info!("[Q-SAFE] Generated new Kyber-1024 keypair for post-quantum channel.");
        Self {
            public_key: pk,
            secret_key: sk,
        }
    }

    /// Encapsulates a shared secret using a peer's public key
    pub fn encapsulate(&self, peer_pk: &PublicKey) -> (SharedSecret, Ciphertext) {
        let (ss, ct) = kyber1024::encapsulate(peer_pk);
        info!("[Q-SAFE] Encapsulated 256-bit symmetric key.");
        (ss, ct)
    }

    /// Decapsulates the ciphertext to retrieve the shared secret
    pub fn decapsulate(&self, ct: &Ciphertext) -> SharedSecret {
        let ss = kyber1024::decapsulate(ct, &self.secret_key);
        info!("[Q-SAFE] Successfully decapsulated shared secret.");
        ss
    }
}
