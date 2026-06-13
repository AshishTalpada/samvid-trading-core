# Security Policy

## Supported Versions

Only the latest release of **Samvid Trading Core** is actively supported for security updates. If you discover a vulnerability, please upgrade to the latest commit on `main` to verify if it has already been resolved.

| Version | Supported |
| ------- | --------- |
| >=1.0.0 | ✅ Yes    |
| <1.0.0  | ❌ No     |

## Reporting a Vulnerability

> [!CAUTION]
> Do NOT open public GitHub issues for security vulnerabilities, especially those exposing API keys, broker connections, or credentials.

We take the security of our trading systems seriously. If you find a security vulnerability (such as a remote code execution vector, authentication bypass, or key leakage risk), please report it to us privately:

1. Send an email to the repository owner/maintainer (or open a private security advisory on GitHub if enabled).
2. Clearly describe the vulnerability, the steps to reproduce it, and the potential impact.
3. Allow up to 48 hours for an initial response.
4. We will work with you to patch the vulnerability and coordinate a responsible public disclosure.

## Hardened Security Practices in Samvid Trading Core

Our architecture includes several built-in security features to protect your keys and funds:

*   **OS Keyring Integration (Vault)**: All sensitive credentials (such as TWS/Gateway passwords, API tokens, and private keys) are stored in the OS credential manager (via the `keyring` package) rather than raw text files.
*   **Log Redaction**: The custom `SovereignFormatter` log handler automatically redacts detected API keys, passwords, and tokens using regular expressions, preventing accidental leakage in debug logs.
*   **Adversarial Payload Guard**: The `PromptGuard` sanitizes incoming external feeds (like TradingView news alerts) to prevent prompt injection or execution of malicious commands.
*   **HMAC Node Authentication**: TCP relay nodes use HMAC-SHA256 authentication with a rotating time-window for multi-process verification.

## Handling Leaked Secrets

If you accidentally commit a `.env` file or expose credentials in log files:
1. Revoke the compromised keys immediately via your Interactive Brokers Portal or MetaTrader 5 broker dashboard.
2. Run a history-purge tool (like `git-filter-repo` or `BFG Repo-Cleaner`) to wipe the secret from git history.
3. Cycle all API connections.
