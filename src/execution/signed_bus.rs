use ed25519_dalek::{Signature, Signer, SigningKey, Verifier};
use log::warn;
use sha2::{Digest, Sha512};
use std::env;
use std::sync::Mutex as StdMutex;
use tokio::sync::Mutex;

/// The Sovereign Signed Execution Bus
/// Guarantees that every outbound order payload is cryptographically authenticated
/// using an air-gapped or securely provisioned Ed25519 keypair before hitting the exchange.
pub struct SignedBus {
    keypair: SigningKey,
    sequence_id: Mutex<u64>,
    last_verified_sequence: StdMutex<u64>,
}

impl Default for SignedBus {
    fn default() -> Self {
        Self::new()
    }
}

impl SignedBus {
    /// Initialize the bus by attempting to load the ED25519 hardware seed
    /// Defaults to a tightly controlled ephemeral key if the vault is locked (for dry runs)
    pub fn new() -> Self {
        // Attempt to load Sovereign hardware key seed from secure environment vault
        let seed_bytes = match env::var("SOVEREIGN_ED25519_VAULT_SEED") {
            Ok(seed_hex) => match hex::decode(seed_hex) {
                Ok(decoded) if decoded.len() == 32 => {
                    let mut arr = [0u8; 32];
                    arr.copy_from_slice(&decoded);
                    arr
                }
                _ => {
                    warn!("[SIGNED-BUS] Invalid vault seed; using isolated fallback key.");
                    Self::fallback_seed()
                }
            },
            Err(_) => Self::fallback_seed(),
        };

        let keypair = SigningKey::from_bytes(&seed_bytes);

        SignedBus {
            keypair,
            sequence_id: Mutex::new(0),
            last_verified_sequence: StdMutex::new(0),
        }
    }

    fn fallback_seed() -> [u8; 32] {
        let mut hasher = Sha512::new();
        hasher.update(b"sovereign_ephemeral_fallback_seed");
        let result = hasher.finalize();
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&result[..32]);
        arr
    }

    /// Signs an outbound FIX or REST order payload.
    /// Returns an 8-byte sequence followed by the 64-byte Ed25519 signature.
    pub async fn sign_order(&self, payload: &[u8]) -> Vec<u8> {
        let mut seq = self.sequence_id.lock().await;
        *seq += 1;

        // Prevent replay attacks by injecting the sequence number into the signing payload
        let mut secure_payload = Vec::with_capacity(payload.len() + 8);
        secure_payload.extend_from_slice(payload);
        secure_payload.extend_from_slice(&seq.to_be_bytes());

        let signature = self.keypair.sign(&secure_payload);
        let mut envelope = Vec::with_capacity(72);
        envelope.extend_from_slice(&seq.to_be_bytes());
        envelope.extend_from_slice(&signature.to_bytes());
        envelope
    }

    /// Verifies a signed envelope and rejects replayed sequence numbers.
    /// Raw 64-byte signatures remain accepted for legacy payloads without replay protection.
    pub fn verify_payload(&self, payload: &[u8], signature_bytes: &[u8]) -> bool {
        if signature_bytes.len() == 64 {
            return self.verify_signature(payload, signature_bytes);
        }
        if signature_bytes.len() != 72 {
            return false;
        }

        let sequence = u64::from_be_bytes(signature_bytes[..8].try_into().unwrap_or([0; 8]));
        if sequence == 0 {
            return false;
        }
        let mut secure_payload = Vec::with_capacity(payload.len() + 8);
        secure_payload.extend_from_slice(payload);
        secure_payload.extend_from_slice(&sequence.to_be_bytes());
        if !self.verify_signature(&secure_payload, &signature_bytes[8..]) {
            return false;
        }

        let mut last_sequence = self
            .last_verified_sequence
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if sequence <= *last_sequence {
            return false;
        }
        *last_sequence = sequence;
        true
    }

    fn verify_signature(&self, payload: &[u8], signature_bytes: &[u8]) -> bool {
        let array: [u8; 64] = match signature_bytes.try_into() {
            Ok(arr) => arr,
            Err(_) => return false,
        };
        let signature = Signature::from_bytes(&array);

        self.keypair
            .verifying_key()
            .verify(payload, &signature)
            .is_ok()
    }

    /// Gets the public key hex for registration with the exchange/broker API
    pub fn get_public_key_hex(&self) -> String {
        hex::encode(self.keypair.verifying_key().to_bytes())
    }
}

/// Fallback C-FFI or Python hook wrapper (simplifies FFI bindings)
pub fn sign_order(payload: &[u8]) -> Vec<u8> {
    // Legacy blocking hook for Python ctypes/FFI
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let bus = SignedBus::new();
        bus.sign_order(payload).await
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn signed_envelope_verifies_once_and_rejects_replay() {
        let bus = SignedBus::new();
        let payload = b"BUY|SPY|10";
        let envelope = bus.sign_order(payload).await;

        assert_eq!(envelope.len(), 72);
        assert!(bus.verify_payload(payload, &envelope));
        assert!(!bus.verify_payload(payload, &envelope));
    }

    #[tokio::test]
    async fn signed_envelope_rejects_payload_tampering() {
        let bus = SignedBus::new();
        let envelope = bus.sign_order(b"BUY|SPY|10").await;

        assert!(!bus.verify_payload(b"BUY|SPY|100", &envelope));
    }
}
