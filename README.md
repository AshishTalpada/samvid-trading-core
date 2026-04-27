# 🪐 Sovereign Trading System V13.7

![License](https://img.shields.io/badge/license-Proprietary-red)
![Version](https://img.shields.io/badge/version-13.7-cyan)
![System](https://img.shields.io/badge/Sovereign-Institutional-blue)

Sovereign is a high-frequency, event-driven autonomous trading engine designed for multi-asset institutional execution. It leverages a mesh of specialized agents to coordinate discovery, vetting, and risk-managed trade execution across IBKR and MT5 backends.

## 🏗️ Architectural Overview

The system operates on an asynchronous event-bus architecture, synchronizing the following core modules:

*   **Dhatu Oracle**: Macro-causation engine mapping global indices (Yields, VIX, Oil) to trade bias.
*   **Trading Brain**: The central nervous system managing state (Scanning, Analyzing, Positioned).
*   **Agent Mesh**:
    *   `Agent A`: Pattern recognition and HFT tick ingestion.
    *   `Agent B`: Sentiment and Dhatu-state classification.
    *   `Agent C`: Execution and Safety (Blackswan protection).
    *   `Agent D`: Evolutionary learning and expectancy matrix optimization.
*   **Intelligent UI**: A real-time React dashboard visualizing the Quorum Matrix and Neural Link telemetry.

## 🚀 Quick Start

### 1. Prerequisites
*   Python 3.10+
*   Node.js 18+
*   QuestDB (for HFT tick storage)
*   SQLite3

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/[YOUR_USERNAME]/TradingSystem.git
cd TradingSystem

# Setup Python environment
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt

# Setup Frontend
cd frontend
npm install
```

### 3. Vault Initialization
Sovereign uses an OS-level secure Vault to store sensitive keys. **Do not store keys in `.env` files.**
```bash
python src/vault_init.py
```

### 4. Running the System
```bash
# Start the Backend
python src/main.py

# Start the Dashboard
cd frontend
npm run dev
```

## 🛡️ Security & Privacy
*   **Zero-Keys Policy**: All API keys are stored in the OS Credential Manager via `keyring`.
*   **Local-First**: Data persistence is handled via local SQLite and QuestDB instances.
*   **HMAC Handshake**: WebSockets are secured via time-synced HMAC-SHA256 tokens.

---
**Disclaimer**: This is institutional-grade software. Trading involves significant risk. Use with caution.
