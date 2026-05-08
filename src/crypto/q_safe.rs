use pqcrypto_kyber::kyber1024::*;
use pqcrypto_traits::kem::{Ciphertext, PublicKey, SecretKey, SharedSecret};
use log::{info, error};

/// Post-Quantum Cryptography Module (Kyber-1024)
/// Secures the Sovereign architecture against future quantum decryption attacks.
pub struct QuantumSafeChannel {
    pub public_key: PublicKey,
    secret_key: SecretKey,
}

impl QuantumSafeChannel {
    pub fn new() -> Self {
        let (pk, sk) = keypair();
        info!("[Q-SAFE] Generated new Kyber-1024 keypair for post-quantum channel.");
        Self {
            public_key: pk,
            secret_key: sk,
        }
    }

    /// Encapsulates a shared secret using a peer's public key
    pub fn encapsulate(&self, peer_pk: &PublicKey) -> (SharedSecret, Ciphertext) {
        let (ss, ct) = encapsulate(peer_pk);
        info!("[Q-SAFE] Encapsulated 256-bit symmetric key.");
        (ss, ct)
    }

    /// Decapsulates the ciphertext to retrieve the shared secret
    pub fn decapsulate(&self, ct: &Ciphertext) -> SharedSecret {
        let ss = decapsulate(ct, &self.secret_key);
        info!("[Q-SAFE] Successfully decapsulated shared secret.");
        ss
    }
}
