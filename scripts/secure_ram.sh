#!/bin/bash
# Sovereign Memory Hardening
# Enables AMD SME (Secure Memory Encryption) if hardware support is detected.

if grep -q "sme" /proc/cpuinfo; then
    echo "[SECURITY] AMD SME hardware detected. Enabling memory isolation..."
    # Enable SME bit in kernel security flags if supported
    if [ -f "/sys/kernel/security/sme" ]; then
        echo "1" > /sys/kernel/security/sme
        echo "[SUCCESS] Transparent Memory Encryption ACTIVE."
    else
        echo "[WARNING] SME supported by CPU but not exposed by current kernel config."
    fi
else
    echo "[CRITICAL] Hardware Memory Encryption (SME/TME) NOT supported by CPU."
    echo "[CRITICAL] System vulnerable to physical DMA/Cold-boot attacks."
fi
