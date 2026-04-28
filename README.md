# 🪐 Samvid Trading Core (v1.0-beta)

[![Build Status](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/main.yml/badge.svg)](https://github.com/AshishTalpada/samvid-trading-core/actions)
[![Latest Release](https://img.shields.io/github/v/tag/AshishTalpada/samvid-trading-core?label=release&color=cyan)](https://github.com/AshishTalpada/samvid-trading-core/releases)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linter](https://img.shields.io/badge/linting-ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-24_suites-green.svg)](#-test-suite--reliability)

**Status: v1.0-beta | Architecture-First Agent Mesh | Event-Driven Execution**

**Samvid** (Sanskrit for *Consensus* or *Shared Intelligence*) is an experimental, event-driven trading engine built around a decentralized mesh of specialized agents. Instead of a monolithic strategy, execution is the result of a consensus-based voting model where multiple specialized entities (Pattern Discovery, Sentiment, Macro Oracle) reach a quorum before any action is taken.

---

## 🚀 Live Demonstration

Experience the "Samvid Intelligence Mesh" telemetry in a zero-dependency terminal simulation.

```bash
# Run the live sovereign demonstration
python src/demonstration.py
```

---

## 🧠 Architecture Overview

Samvid is designed for modularity and high-frequency event processing:

*   **Autonomous Agent Mesh**: 11 specialized agents (e.g., Pattern Atlas, Belief Tracker) communicate via an internal Intelligence Bus.
*   **Consensus-Based Quorum**: No single agent can execute a trade; a quorum-based matrix ensures that technical, macro, and risk parameters are all satisfied.
*   **Dhatu Macro Oracle**: A causation-focused state machine mapping macro variables (Yields, VIX, Energy) into 5 distinct market regimes (Vriddhi, Sthiti, Kshaya, etc.).
*   **Zero-Keys Security**: Credential management is handled via an OS-level secure vault (keyring) ensuring no plaintext secrets ever touch the disk.

### Data Flow & Quorum
```mermaid
graph TD
    Market[Market Data / HFT Ticks] --> Bus[Intelligence Bus]
    Bus --> AgentA[Agent A: Pattern Discovery]
    Bus --> AgentB[Agent B: Sentiment Classifier]
    AgentA --> Quorum{Samvid Quorum Matrix}
    AgentB --> Quorum
    Dhatu[Dhatu Macro Oracle] --> Quorum
    Quorum -->|Consensus Reached| AgentC[Agent C: MT5/IBKR Executor]
    AgentC --> Safety[Blackswan / Risk Guard]
    Safety -->|Pass| Trade[Trade Execution]
```

---

## 🖼️ Dashboard Preview

![Live Dashboard](docs/images/dashboard_live.png)
*Live v1.0-beta Intelligence Dashboard showing real-time agent consensus and macro state synthesis.*

---

## 🧪 Test Suite & Reliability

The system is backed by a comprehensive suite of **24 test modules** covering unit, integration, and high-load stress testing:

*   **Stress Testing**: Modules like `stress_test_500k.py` validate the Intelligence Bus under extreme message loads.
*   **Behavioral Logic**: `test_behavioral_logic.py` ensures agents adhere to the consensus protocol.
*   **Risk Invariants**: `test_risk_invariants.py` strictly enforces position sizing and stop-loss rules.
*   **Integration**: End-to-end flows from data ingestion to mock execution are validated in `test_integration.py`.

```bash
# Run the full test suite
pytest tests/
```

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.10+ (Asyncio), FastAPI, Uvicorn |
| **Frontend** | React 18, Vite, Framer Motion, Lightweight Charts |
| **Databases** | QuestDB (Time-series Ticks), SQLite3 (System State) |
| **Security** | OS Vault (keyring), HMAC-SHA256, WebSocket Handshake |

---

## 🚀 Getting Started

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/AshishTalpada/samvid-trading-core.git
cd samvid-trading-core

# Quick Setup via Makefile
make setup
```

### 2. Execution
```bash
# Spin up infrastructure (QuestDB)
make docker-up

# Start the full stack
make dev
```

---

## 🛡️ License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Disclaimer**: *This project is for research and educational purposes only. Algorithmic trading involves substantial risk. Use responsibly.*

