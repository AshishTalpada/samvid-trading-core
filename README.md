<div align="center">

<h1>⚡ Samvid Trading Core</h1>

<p><strong>Open-source, experimental AI multi-agent algorithmic trading system<br>
for Interactive Brokers &amp; MetaTrader 5</strong></p>

[![Main Build](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/main.yml/badge.svg)](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/main.yml)
[![Quality Gate](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/quality.yml/badge.svg)](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/quality.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-native%20layer-000000?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![IBKR Paper](https://img.shields.io/badge/IBKR-Paper%20Execution-009900)](https://www.interactivebrokers.com/)
[![MT5](https://img.shields.io/badge/MetaTrader5-FTMO%20Ready-blue)](https://www.metatrader5.com/)
[![Telegram Alerts](https://img.shields.io/badge/Telegram-Live%20Alerts-2CA5E0?logo=telegram)](https://telegram.org/)
[![QuestDB](https://img.shields.io/badge/QuestDB-Time%20Series-FF6B35)](https://questdb.io/)
[![Stars](https://img.shields.io/github/stars/AshishTalpada/samvid-trading-core?style=social)](https://github.com/AshishTalpada/samvid-trading-core/stargazers)
[![Forks](https://img.shields.io/github/forks/AshishTalpada/samvid-trading-core?style=social)](https://github.com/AshishTalpada/samvid-trading-core/fork)

<p>
<a href="#-quick-start">Quick Start</a> •
<a href="#-architecture">Architecture</a> •
<a href="#-features">Features</a> •
<a href="#-agents">Agents</a> •
<a href="#-installation">Installation</a> •
<a href="#-configuration">Configuration</a> •
<a href="#-contributing">Contributing</a>
</p>

</div>

---

> **Samvid Trading Core** is a backend-first, consensus-driven algorithmic trading engine. It combines 11 specialized AI agents, an async pub/sub intelligence bus, multi-broker execution (IBKR + MT5), real-time data pipelines, institutional-grade risk management, and Telegram operator alerts — all in a single open-source Python + Rust stack.

> ⚠️ **Disclaimer**: This is trading research and engineering software, not financial advice. Paper trading mode (`TRADING_MODE=ibkr_paper`) is the default. Live trading requires independent validation, broker permissions, and capital-risk controls you are solely responsible for.

---

<div align="center">

### ⭐ If Samvid saves you time or teaches you something, please [star the repo](https://github.com/AshishTalpada/samvid-trading-core/stargazers) — it helps other traders and developers find it.

</div>

---

## 📑 Table of Contents

- [Why Samvid Trading Core?](#-why-samvid-trading-core)
- [Features](#-features)
  - [Multi-Agent AI Consensus Engine](#-multi-agent-ai-consensus-engine)
  - [Real-Time Data Pipeline](#-real-time-data-pipeline)
  - [Institutional-Grade Risk Management](#-institutional-grade-risk-management)
  - [Broker Integration](#-broker-integration)
  - [Intelligence Bus](#-intelligence-bus)
  - [Security](#-security)
  - [Operator Experience](#-operator-experience)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Running Tests](#-running-tests)
- [Configuration](#-configuration)
- [Tech Stack](#-tech-stack)
- [Contributing](#-contributing)
- [Roadmap](#-roadmap)
- [License](#-license)
- [Support the Project](#-support-the-project)

---

## 🌟 Why Samvid Trading Core?

Most open-source trading bots stop at "buy when RSI crosses 30." Samvid goes further:

| What basic bots do | What Samvid does |
|---|---|
| Static indicators → market order | Pattern detection + regime + oracle + 11-agent quorum → friction-gated broker paper order |
| Assumed data freshness | Explicitly proven fresh bars or realtime quote before every entry |
| Fire-and-forget orders | IBKR order ID capture → broker state reconciliation → orphan detection |
| No learning | `trade.exit` events feed calibration matrix, alpha-health, and expectancy |
| Terminal logs only | Logs + runtime health + Telegram alerts + CI validation + audit reports |
| Unknown restart behavior | Startup validation, PID singleton lock, watchdogs, restart audit tooling |
| Flat risk | Drawdown ladder, consecutive-loss escalation, oracle freeze, cost-aware exit engine |

---

## ✨ Features

### 🤖 Multi-Agent AI Consensus Engine
- **11 specialized agents** (A through H + advisory) vote on every trade entry
- Agent A: Chart pattern detection (Bull Flag, Cup & Handle, Head & Shoulders, Gap Fill, etc.)
- Agent B: Bayesian belief tracking + Dhatu Oracle macro regime synthesis
- Agent C (IBKR): F6 8-step position sizing chain + Black Swan Protocol circuit breaker
- Agent C (MT5): FTMO compliance layer + prop firm trade management
- Agent D: Live learning engine — expectancy, alpha-health, calibration matrix
- Agent E: Correlation guard — sector exposure limits
- Advisory: Contrarian, Chaos, Contagion Sentinel, Audit agents (non-blocking signals)

### 📊 Real-Time Data Pipeline
- TradingView WebSocket quote streamer (fast tick lane)
- OHLCV multi-timeframe ingestion (1m / 5m / 15m / 1h)
- OpenBB + yfinance provider with automatic fallback
- VIX + macro context + news sentiment lane
- QuestDB time-series adapter for high-throughput candle storage
- After-hours compact backfill mode

### 🛡️ Institutional-Grade Risk Management
- **DrawdownLadder**: 4-level escalation (NORMAL → YELLOW → ORANGE → RED → CIRCUIT BREAKER)
- **ConsecutiveLossTracker**: Graduated 5-level response (size reduction → reduce-only → paper lock → audit)
- **MorningBudget**: Regime-aware daily trade and risk budget generator
- **ExitIntelligence**: 6-priority exit engine (hard stop → trailing stop → target/partial → daily loss → VIX spike → belief collapse)
- **RiskInvariants**: Tamper-proof constant checker — AI agents cannot override hard limits
- **OrderThrottler**: Token-bucket rate limiter (30 orders / 60 seconds)
- **VIXProtocol**: Volatility circuit breaker
- **BlackSwanProtocol**: Halts new trade discovery on correlated crash events

### 🔌 Broker Integration
- **Interactive Brokers (IBKR)**: Paper + live execution via ib-insync, TWS/Gateway at `127.0.0.1:7497`
- **MetaTrader 5**: FTMO prop firm compliant execution (2 trades/day hard cap)
- Broker reconciliation: local state vs broker state comparison, stale/orphan/rejected order detection
- Execution evidence: every order decision is stored with full context for audit

### 🧠 Intelligence Bus
- Priority pub/sub async event bus (`SharedIntelligenceBus`)
- HMAC-SHA256 authenticated TCP relay for multi-process/multi-node architectures
- Weak-reference subscriber cleanup to prevent memory leaks
- Per-topic priority routing: `oracle.freeze` (P0) → `trade.exit` (P1) → `tick.hft` (P5) → `candle.batch` (P12)

### 🔐 Security
- OS Keyring vault (Windows Credential Manager) for all secrets
- Log redaction — credentials never appear in log files
- Adversarial news payload guard (PromptGuard)
- Non-root Docker user + multi-stage Dockerfile
- Atomic PID singleton lock (`O_EXCL`) prevents duplicate instances

### 📡 Operator Experience
- Telegram bot for startup, execution, rejection, exit, DMS, and health alerts
- REST API server (FastAPI + uvicorn) on port 8000 with `/health/live` endpoint
- Prometheus metrics on port 9090
- Startup profiler (millisecond-level component timing)
- Watchdog task that pings the operator if the system goes quiet

---

## 🏗️ Architecture

```
                      MARKET + CONTEXT INPUTS
  ─────────────────────────────────────────────────────────────────
  TradingView quotes │ OHLCV pipeline │ IBKR snapshots │ News/Macro
          │                 │                │                │
          └─────────────────┴────────────────┴────────────────┘
                                    │
                                    ▼
                       SharedIntelligenceBus (async pub/sub)
                        priority-routed, HMAC-authenticated
                                    │
                                    ▼
                            TradingBrain
                  ┌─────────────────────────────────┐
                  │  Regime detection │ Scan loop   │
                  │  DrawdownLadder   │ MorningBudget│
                  │  OracleGate       │ QuantConsensus│
                  └─────────────────────────────────┘
                                    │
                                    ▼
                          TradingCoordinator
               ┌──────────────────────────────────────┐
               │ 11-Agent Quorum │ Freshness Proof     │
               │ Risk Gates      │ Position Sizing (F6)│
               │ Friction Veto   │ Execution Evidence  │
               └──────────────────────────────────────┘
                          │               │
               ┌──────────┘               └──────────┐
               ▼                                     ▼
      IBKR Paper Order                       Decision rejection
      (order ID captured)                  (evidence stored)
               │                                     │
               └──────────────┬──────────────────────┘
                              ▼
               SQLite evidence + QuestDB time-series
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       Telegram alerts          Post-trade learning
                             (expectancy + calibration)
```

### Directory Map

| Path | Purpose |
|---|---|
| `src/main.py` | Entry point: mode safety, broker connections, watchdogs, metrics |
| `src/brain.py` | Main orchestrator: state machine, scan loop, oracle gate |
| `src/coordinator.py` | Entry quorum, risk gates, F6 sizing, broker routing |
| `src/agent_a.py` | Pattern detection, regime classification, entropy scoring |
| `src/agent_b.py` | Bayesian belief tracking, Dhatu Oracle integration |
| `src/agent_c_ibkr.py` | IBKR execution, Black Swan, VIX protocol, position sizing |
| `src/agent_c_mt5.py` | MT5 / FTMO compliance execution |
| `src/agent_d.py` | Live learning, expectancy matrix, alpha-health |
| `src/exit_intelligence.py` | 6-priority exit engine with cost-awareness |
| `src/risk_invariants.py` | Tamper-proof risk constant checker |
| `src/intelligence_bus.py` | Priority async pub/sub event bus |
| `src/brain_state.py` | DrawdownLadder, ConsecutiveLossTracker, MorningBudget |
| `src/data_pipeline.py` | OHLCV, macro, news, VIX ingestion |
| `src/dhatu_oracle.py` | Macro regime synthesis engine |
| `src/vault.py` | OS keyring secrets manager |
| `src/api_server.py` | FastAPI REST API + Prometheus metrics |
| `src/telegram_alerts.py` | Telegram operator alert transport |
| `migrations/` | Versioned SQLite schema migrations with rollback |
| `scripts/` | Preflight, startup validation, audit, diagnostic tools |
| `tests/` | 94-file test suite: risk, execution, health, integration |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://github.com/astral-sh/uv) package manager
- Interactive Brokers TWS or IB Gateway (for `ibkr_paper` mode)
- Telegram bot token (optional, for alerts)

### 1. Clone

```bash
git clone https://github.com/AshishTalpada/samvid-trading-core.git
cd samvid-trading-core
```

### 2. Install

```bash
pip install uv
uv sync --locked
```

### 3. Configure secrets

```bash
# Store credentials in the OS keyring vault
python src/vault.py set IBKR_ACCOUNT_ID "your_account_id"
python src/vault.py set TELEGRAM_BOT_TOKEN "your_bot_token"
python src/vault.py set TELEGRAM_CHAT_ID "your_chat_id"
```

Or copy `.env.example` to `.env` and fill in the values (development only).

### 4. Run preflight validation

```bash
uv run python scripts/startup_validation.py
```

### 5. Launch in paper mode (no broker required)

```bash
uv run python src/main.py
```

### 6. Launch with IBKR paper execution

```powershell
$env:TRADING_MODE = "ibkr_paper"
uv run python src/main.py
```

> Make sure TWS / IB Gateway is running and listening on port `7497` before launching.

---

## 🧪 Running Tests

```bash
# Full test suite
uv run python -m pytest tests/ -q --tb=short

# With coverage report
uv run python -m pytest tests/ --cov=src --cov-report=term-missing

# Key test modules
uv run python -m pytest tests/test_risk_invariants.py tests/test_dms.py -v

# Lint check
uv run ruff check src/ tests/ scripts/

# Compile check (syntax only, no imports)
uv run python -m compileall -q src/ tests/ scripts/

# Import cycle detection
uv run python scripts/detect_cycles.py
```

---

## ⚙️ Configuration

### Trading Modes

| Mode | Broker | Orders | Use Case |
|---|---|---|---|
| `paper` | None | Internal simulation | Safe local smoke tests |
| `ibkr_paper` | IBKR TWS/Gateway paper account | Real paper orders | Primary operational mode |
| `live` | IBKR live account | Real live orders | Requires `ALLOW_FORCE_LIVE=1` |

### Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `TRADING_MODE` | `ibkr_paper` | Trading mode selector |
| `ALLOW_FORCE_LIVE` | `0` | Must be `1` to enable live mode |
| `SOVEREIGN_SKIP_PID_CHECK` | `0` | Set to `1` in tests to bypass singleton lock |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token (store in vault) |
| `TELEGRAM_CHAT_ID` | — | Telegram destination chat ID |
| `QUESTDB_ENABLED` | auto-detect | Enable QuestDB time-series adapter |
| `TOTAL_CAPITAL` | `500.0` | Starting capital for position sizing |
| `IBKR_MAX_TRADES_PER_DAY` | `20` | IBKR daily trade cap |

Full variable reference: see [`src/config.py`](src/config.py) and [`.env.example`](.env.example).

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Core language | Python 3.11 / 3.12 |
| Native performance | Rust (PyO3), C extensions (Cython), CUDA kernels |
| Math / signals | NumPy, Polars, SciPy, Numba JIT |
| ML / learning | HMMlearn, ChromaDB (vector memory), fastembed |
| Broker APIs | ib-insync (IBKR), MetaTrader5 (Windows) |
| Market data | OpenBB, yfinance, TradingView WebSocket |
| Web API | FastAPI + uvicorn |
| Time-series DB | QuestDB (high-throughput) + SQLite (durable record) |
| Database ORM | yoyo-migrations (versioned schema) |
| Secrets | OS keyring (Windows Credential Manager) |
| Alerts | Telegram Bot API |
| Observability | Prometheus metrics, structured logging, runtime health snapshots |
| CI/CD | GitHub Actions (lint + test + Rust + Node frontend) |
| Containerization | Docker (multi-stage, non-root) + Docker Compose |
| Package manager | uv (fast, reproducible, locked) |

---

## 📈 Roadmap

- [ ] Verified positive expectancy after costs across 90-day paper soak
- [ ] WebSocket-based live dashboard (frontend/)
- [ ] More pattern detectors (VWAP reclaim, opening range breakout)
- [ ] Backtesting engine integration with walk-forward validation
- [ ] Multi-account portfolio manager
- [ ] Options chain scanner (option_agent.py)
- [ ] PostgreSQL migration path (away from SQLite for high-frequency writes)

---

## 📜 License

MIT License — see [`LICENSE`](LICENSE) for details.

Copyright © 2026 Ashishkumar Talpada

---

## ⭐ Support the Project

If Samvid Trading Core is useful to you, please consider:
- ⭐ **Starring this repository** — it helps others find it
- 🐛 **Reporting bugs** via [GitHub Issues](https://github.com/AshishTalpada/samvid-trading-core/issues)
- 💡 **Suggesting features** or submitting PRs
- 📣 **Sharing it** with your quant/trading developer community

**One-click share** (copy and post on X/Twitter, LinkedIn, or Discord):

> Just discovered Samvid Trading Core — an open-source, multi-agent AI algorithmic trading engine with IBKR + MT5 paper trading, risk management, and Telegram alerts. Built in Python + Rust. Check it out: https://github.com/AshishTalpada/samvid-trading-core

**Sponsor the author** to support ongoing development — add your sponsor link or Buy Me A Coffee URL here.

---

## 📚 Related Projects & Keywords

**Algorithmic trading** • **trading bot** • **automated trading system** • **Interactive Brokers bot** • **IBKR Python** • **MetaTrader 5 Python** • **FTMO trading bot** • **quantitative finance** • **quant trading** • **multi-agent trading AI** • **AI trading system** • **machine learning trading** • **backtesting framework** • **Python trading bot** • **open source trading bot** • **stock trading bot** • **forex trading bot** • **risk management system** • **position sizing** • **paper trading** • **live trading** • **real-time market data** • **FastAPI trading** • **Rust trading** • **QuestDB** • **Telegram trading alerts** • **consensus trading** • **Bayesian trading** • **regime detection** • **pattern recognition trading**

---

<div align="center">
<sub>Built with ❤️ for the open-source quant community</sub>
</div>
