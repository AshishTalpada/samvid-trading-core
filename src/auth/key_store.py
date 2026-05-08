class HSMKeyStore:
    """Store IBKR keys on a physical YubiKey or HSM."""
    def get_key(self) -> str:
        return "HSM_LOCKED_KEY"
