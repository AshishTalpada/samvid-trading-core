#!/bin/bash
# Sovereign State Vault Backup
# Compresses and GPG-encrypts the entire brain state before offloading.

BACKUP_DIR="/data/brain_state/"
VAULT_PATH="/mnt/offline_vault/brain_state_$(date +%F).tar.gz.gpg"
SOVEREIGN_PUBKEY="sovereign_admin@internal.system"

echo "[BACKUP] Initiating encrypted state backup..."

if [ ! -d "$BACKUP_DIR" ]; then
    echo "[ERROR] Source directory $BACKUP_DIR not found."
    exit 1
fi

# Compress and encrypt on the fly to avoid plain-text temp files
tar -cz $BACKUP_DIR | gpg --encrypt --recipient "$SOVEREIGN_PUBKEY" --trust-model always -o "$VAULT_PATH"

if [ $? -eq 0 ]; then
    echo "[SUCCESS] State backup secured at $VAULT_PATH"
else
    echo "[ERROR] Backup encryption failed."
    exit 1
fi
