# Samvid Trading Core

**Open-source, experimental AI multi-agent algorithmic trading system for Interactive Brokers (IBKR) & MetaTrader 5 (MT5).**

Samvid Trading Core is a backend-first, consensus-driven algorithmic trading engine that combines 11 specialized AI agents, an async pub/sub intelligence bus, multi-broker execution (IBKR + MT5), real-time data pipelines, institutional-grade risk management, and Telegram operator alerts — all in a single open-source Python + Rust stack.

---

## What Makes Samvid Different?

Most open-source trading bots stop at basic RSI crossovers. Samvid goes further with a **multi-agent consensus quorum**, **institutional risk machinery**, and **broker-state reconciliation** that rivals proprietary quant shops.

| Capability | Samvid Trading Core |
|---|---|
| Trade entry logic | Pattern detection + regime classification + oracle + 11-agent quorum → friction-gated order |
| Data freshness | Explicitly proven fresh bars or realtime quote before every entry |
| Order lifecycle | IBKR order ID capture → broker state reconciliation → orphan detection |
| Learning loop | `trade.exit` events feed calibration matrix, alpha-health, and expectancy |
| Observability | Logs + runtime health + Telegram alerts + CI validation + audit reports |
| Resilience | Startup validation, PID singleton lock, watchdogs, restart audit tooling |
| Risk controls | Drawdown ladder, consecutive-loss escalation, oracle freeze, cost-aware exit engine |

---

## Core Features

### Multi-Agent AI Consensus Engine
- **11 specialized agents** (A through H + advisory) vote on every trade entry
- Agent A: Chart pattern detection (Bull Flag, Cup & Handle, Head & Shoulders, Gap Fill)
- Agent B: Bayesian belief tracking + Dhatu Oracle macro regime synthesis
- Agent C (IBKR): F6 8-step position sizing chain + Black Swan Protocol circuit breaker
- Agent C (MT5): FTMO compliance layer + prop firm trade management
- Agent D: Live learning engine — expectancy, alpha-health, calibration matrix
- Agent E: Correlation guard — sector exposure limits
- Advisory: Contrarian, Chaos, Contagion Sentinel, Audit agents

### Real-Time Data Pipeline
- TradingView WebSocket quote streamer (fast tick lane)
- OHLCV multi-timeframe ingestion (1m / 5m / 15m / 1h)
- OpenBB + yfinance provider with automatic fallback
- VIX + macro context + news sentiment lane
- QuestDB time-series adapter for high-throughput candle storage

### Institutional-Grade Risk Management
- **DrawdownLadder**: 4-level escalation (NORMAL → YELLOW → ORANGE → RED → CIRCUIT BREAKER)
- **ConsecutiveLossTracker**: Graduated 5-level response (size reduction → reduce-only → paper lock → audit)
- **MorningBudget**: Regime-aware daily trade and risk budget generator
- **ExitIntelligence**: 6-priority exit engine (hard stop → trailing stop → target/partial → daily loss → VIX spike → belief collapse)
- **RiskInvariants**: Tamper-proof constant checker — AI agents cannot override hard limits
- **OrderThrottler**: Token-bucket rate limiter (30 orders / 60 seconds)
- **VIXProtocol**: Volatility circuit breaker
- **BlackSwanProtocol**: Halts new trade discovery on correlated crash events

### Broker Integration
- **Interactive Brokers (IBKR)**: Paper + live execution via ib-insync, TWS/Gateway at `127.0.0.1:7497`
- **MetaTrader 5**: FTMO prop firm compliant execution (2 trades/day hard cap)
- Broker reconciliation: local state vs broker state comparison, stale/orphan/rejected order detection
- Execution evidence: every order decision is stored with full context for audit

---

## Architecture Overview

```
                  MARKET + CONTEXT INPUTS
  ─────────────────────────────────────────────────────────────
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

---

## Tech Stack

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

## Quick Start

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
python src/vault.py set IBKR_ACCOUNT_ID "your_account_id"
python src/vault.py set TELEGRAM_BOT_TOKEN "your_bot_token"
python src/vault.py set TELEGRAM_CHAT_ID "your_chat_id"
```

Or copy `.env.example` to `.env` and fill in the values (development only).

### 4. Run preflight validation

```bash
uv run python scripts/startup_validation.py
```

### 5. Launch in paper mode

```bash
uv run python src/main.py
```

### 6. Launch with IBKR paper execution

```powershell
$env:TRADING_MODE = "ibkr_paper"
uv run python src/main.py
```

Make sure TWS / IB Gateway is running and listening on port `7497` before launching.

---

## Running Tests

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
```

---

## Documentation

- [Architecture Deep Dive](architecture.md)
- [Operations Guide](ops_guide.md)
- [GitHub SEO & Discoverability Guide](github_seo_guide.md)
- [Security & Vault Setup](security/vault.md)
- [Physical Security](security/physical.md)

---

## License

MIT License — see [LICENSE](https://github.com/AshishTalpada/samvid-trading-core/blob/main/LICENSE) for details.

Copyright © 2026 Ashishkumar Talpada

---

## Related Keywords

Algorithmic trading, trading bot, automated trading system, Interactive Brokers bot, IBKR Python, MetaTrader 5 Python, FTMO trading bot, quantitative finance, quant trading, multi-agent trading AI, AI trading system, machine learning trading, Python trading bot, open source trading bot, stock trading bot, forex trading bot, risk management system, position sizing, paper trading, live trading, real-time market data, FastAPI trading, Rust trading, QuestDB, Telegram trading alerts, consensus trading, Bayesian trading, regime detection, pattern recognition trading, trading dashboard, institutional trading, prop firm trading, automated backtesting.
