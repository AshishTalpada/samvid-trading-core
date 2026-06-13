use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use sha2::{Digest, Sha256};
use std::fs::OpenOptions;
use std::io::{Read, Write};

pub struct ColdWallet {
    pub balance: f64,
    pub public_key: String,
    offline_vault_path: String,
}

impl ColdWallet {
    pub fn new(public_key: &str, vault_path: &str) -> Self {
        ColdWallet {
            balance: 0.0,
            public_key: public_key.to_string(),
            offline_vault_path: vault_path.to_string(),
        }
    }

    /// Syncs profits over a specified threshold securely to an air-gapped ledger format.
    pub fn sync_cold_wallet(&mut self, amount: f64, signature: &[u8]) -> bool {
        if !amount.is_finite() || amount < 10000.0 {
            return false; // Below threshold
        }

        let public_key_bytes: [u8; 32] = match hex::decode(&self.public_key)
            .ok()
            .and_then(|bytes| bytes.try_into().ok())
        {
            Some(bytes) => bytes,
            None => return false,
        };
        let signature_bytes: [u8; 64] = match signature.try_into() {
            Ok(bytes) => bytes,
            Err(_) => return false,
        };
        let verifying_key = match VerifyingKey::from_bytes(&public_key_bytes) {
            Ok(key) => key,
            Err(_) => return false,
        };
        let signature = Signature::from_bytes(&signature_bytes);
        let payload = self.signing_payload(amount);
        if verifying_key.verify(&payload, &signature).is_err() {
            return false;
        }

        let mut hasher = Sha256::new();
        hasher.update(&payload);
        hasher.update(signature_bytes);
        let record_id = format!("{:x}", hasher.finalize());

        if let Ok(mut existing) = OpenOptions::new().read(true).open(&self.offline_vault_path) {
            let mut contents = String::new();
            if existing.read_to_string(&mut contents).is_err()
                || contents.lines().any(|line| line.contains(&record_id))
            {
                return false;
            }
        }

        if let Ok(mut file) = OpenOptions::new()
            .append(true)
            .create(true)
            .open(&self.offline_vault_path)
        {
            let record = format!(
                "TRANSFER: {} to {} | RECORD_ID: {}\n",
                amount, self.public_key, record_id
            );
            if file.write_all(record.as_bytes()).is_ok() && file.sync_data().is_ok() {
                self.balance += amount;
                return true;
            }
        }

        false
    }

    pub fn signing_payload(&self, amount: f64) -> Vec<u8> {
        let mut payload = b"SAMVID_COLD_WALLET_V1\0".to_vec();
        payload.extend_from_slice(self.public_key.as_bytes());
        payload.push(0);
        payload.extend_from_slice(&amount.to_be_bytes());
        payload
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_TEST_LEDGER: AtomicU64 = AtomicU64::new(0);

    fn test_wallet() -> (ColdWallet, SigningKey, String) {
        let signing_key = SigningKey::from_bytes(&[7_u8; 32]);
        let public_key = hex::encode(signing_key.verifying_key().as_bytes());
        let unique = NEXT_TEST_LEDGER.fetch_add(1, Ordering::Relaxed);
        let path = std::env::temp_dir()
            .join(format!(
                "samvid-cold-wallet-{}-{unique}.ledger",
                std::process::id()
            ))
            .to_string_lossy()
            .into_owned();
        let _ = fs::remove_file(&path);
        (ColdWallet::new(&public_key, &path), signing_key, path)
    }

    #[test]
    fn valid_signature_records_transfer_once() {
        let (mut wallet, signing_key, path) = test_wallet();
        let amount = 10_000.0;
        let signature = signing_key.sign(&wallet.signing_payload(amount));

        assert!(wallet.sync_cold_wallet(amount, &signature.to_bytes()));
        assert!(!wallet.sync_cold_wallet(amount, &signature.to_bytes()));
        assert_eq!(wallet.balance, amount);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn invalid_signature_and_amount_fail_closed() {
        let (mut wallet, signing_key, path) = test_wallet();
        let wrong_key = SigningKey::from_bytes(&[8_u8; 32]);
        let amount = 10_000.0;
        let wrong_signature = wrong_key.sign(&wallet.signing_payload(amount));
        let valid_signature = signing_key.sign(&wallet.signing_payload(amount));

        assert!(!wallet.sync_cold_wallet(amount, &wrong_signature.to_bytes()));
        assert!(!wallet.sync_cold_wallet(f64::NAN, &valid_signature.to_bytes()));
        assert!(!wallet.sync_cold_wallet(9_999.0, &valid_signature.to_bytes()));
        assert!(!std::path::Path::new(&path).exists());
    }
}
