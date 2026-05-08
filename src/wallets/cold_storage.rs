use sha2::{Sha256, Digest};
use std::fs::{File, OpenOptions};
use std::io::Write;

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
        if amount < 10000.0 {
            return false; // Below threshold
        }
        
        // 1. Verify multi-sig requirement (Stubbed cryptographic check)
        let mut hasher = Sha256::new();
        hasher.update(amount.to_be_bytes());
        let digest = hasher.finalize();
        
        if signature.len() < 64 {
            println!("[SECURITY] Rejected: Invalid Signature Length for Cold Transfer.");
            return false;
        }

        // 2. Air-gapped File Ledger Append
        if let Ok(mut file) = OpenOptions::new().append(true).create(true).open(&self.offline_vault_path) {
            let record = format!("TRANSFER: {} to {} | HASH: {:x}\n", amount, self.public_key, digest);
            if file.write_all(record.as_bytes()).is_ok() {
                self.balance += amount;
                println!("[COLD_WALLET] Successfully synced {} to Vault.", amount);
                return true;
            }
        }

        false
    }
}
