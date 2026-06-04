# Samvid Trading Core

Open-source AI trading system for Interactive Brokers, MetaTrader 5, paper trading, market-data monitoring, execution safety, and quantitative strategy research.

Samvid Trading Core is a Python-first algorithmic trading platform designed for serious solo builders who want a transparent backend for signal discovery, broker execution, risk controls, trade reconciliation, and operator observability. The project combines real-time market data ingestion, multi-agent decision review, IBKR paper/live routing safeguards, MT5 connectivity, Telegram alerts, execution evidence, and post-trade learning.

> Trading is risky. This software is research infrastructure, not financial advice. Use paper trading, broker safeguards, and independent review before risking capital.

## What This Project Does

- Runs an AI-assisted trading brain for equities, options-adjacent workflows, and multi-broker automation.
- Connects to Interactive Brokers TWS or IB Gateway for IBKR paper trading and controlled live execution.
- Supports MetaTrader 5 connectivity for broker-aware runtime checks and future FX workflows.
- Ingests market data from multiple lanes, including OHLCV data, broker snapshots, and real-time tick streams.
- Applies risk controls before entries, during open positions, and after realized losses.
- Reconciles local trade state against broker reality to detect stale, orphaned, or unmanaged positions.
- Publishes clean Telegram notifications for trade exits, broker issues, runtime health, and operator review.
- Tracks post-trade performance, alpha decay, execution evidence, and promotion readiness.

## Core Keywords

AI trading system, algorithmic trading bot, Interactive Brokers trading bot, IBKR paper trading, MetaTrader 5 automation, Python trading system, quantitative trading platform, multi-agent trading AI, execution risk management, automated trading backend, paper trading framework, trading reconciliation engine, Telegram trading alerts, real-time market data pipeline.

## Architecture Overview

Samvid Trading Core is organized around a backend-first execution architecture:

- `src/main.py` starts the system, safety defaults, broker connections, market-data services, and watchdogs.
- `src/brain.py` coordinates market scanning, state transitions, risk checks, and position lifecycle.
- `src/coordinator.py` performs entry vetting, quorum logic, broker routing, and market-data proof checks.
- `src/brain_position.py` manages open positions, exit intelligence, trade-finalization alerts, and realized PnL.
- `src/brain_reconcile.py` compares database state against broker reality and marks stale rows safely.
- `src/agent_c_ibkr.py` handles Interactive Brokers order routing, audit logs, order recovery, and durable order state.
- `src/agent_d.py` learns from `trade.exit` events and updates calibration and alpha-health telemetry.
- `src/data_pipeline.py` manages OHLCV, tick, news, and provider fallback paths.
- `src/tv_quote_streamer.py` provides a real-time quote lane for fast market updates where configured.

## Broker And Data Support

| Area | Status |
| --- | --- |
| IBKR TWS / IB Gateway | Supported for paper mode and guarded live mode |
| IBKR paper trading | Primary execution validation path |
| MetaTrader 5 | Optional Windows integration |
| TradingView quote stream | Real-time quote lane when enabled |
| yfinance / OHLCV fallback | Supported for lower-frequency data |
| QuestDB | Optional high-throughput market-data storage |
| Telegram | Operator alerts and remote status workflows |
| SQLite | Local trade, evidence, and migration state |

## Safety And Risk Controls

This system is intentionally conservative around live execution:

- Paper mode is the default safe path.
- Live mode requires explicit authorization.
- Entries require recent verified market-data proof.
- Fresh real-time ticks can satisfy entry proof when OHLCV bars lag.
- Consecutive losses trigger reduce-only, paper/recovery lock, or audit-required states.
- Catastrophic R-multiple outliers are clamped for learning while preserving actual PnL.
- Broker reconciliation does not fabricate PnL when live prices are unavailable.
- Missing active IBKR orders receive a broker-settlement grace window before manual reconciliation.

## Telegram Trade Alerts

Trade finalization alerts include operator-useful context:

- Symbol and account
- Position size
- Entry and exit price
- Strategy intent
- Pattern name
- Exit method
- Price source
- Net PnL
- R multiple
- Session PnL

This avoids vague alerts and makes it easier to understand why a trade closed.

## Setup

Use Python 3.11 or 3.12.

```bash
uv sync
```

Run lint and tests:

```bash
uv run ruff check src/ tests/ scripts/
uv run python -m pytest tests -q
```

Run startup validation:

```bash
uv run python scripts/startup_validation.py
```

Run the system in paper mode:

```bash
set TRADING_MODE=paper
uv run python src/main.py
```

On PowerShell:

```powershell
$env:TRADING_MODE = "paper"
uv run python src/main.py
```

## Important Environment Variables

| Variable | Purpose |
| --- | --- |
| `TRADING_MODE` | `paper`, `ibkr_paper`, or `live` |
| `ALLOW_FORCE_LIVE` | Must be `1` to permit live mode |
| `SOVEREIGN_SKIP_PID_CHECK` | Test-only singleton bypass |
| `SOVEREIGN_TV_QUOTES_ENABLED` | Enable or disable TradingView quote lane |
| `SOVEREIGN_IBKR_ACTIVE_ORDER_GRACE_SEC` | Grace window for active IBKR orders missing from snapshots |
| `SOVEREIGN_ENTRY_DATA_PROOF_MAX_AGE_SEC` | Max age for entry market-data proof |
| `TELEGRAM_BOT_TOKEN` | Telegram alert bot token |
| `TELEGRAM_CHAT_ID` | Telegram destination chat ID |

## Production Readiness Position

Samvid Trading Core is a serious trading-system prototype with production-oriented backend components. It is not a hedge-fund production platform yet.

Before live capital, prove the following:

- Stable IBKR paper trading over many sessions
- Positive expectancy after commission, slippage, and rejects
- Complete execution evidence
- Clean reconciliation history
- No stale order state
- No unreviewed broker orphan positions
- Real-time data reliability under market hours
- Operator alerts that are actionable and not noisy
- Disaster recovery and restart behavior

## Development Workflow

Recommended checks before every push:

```bash
uv run ruff check src/ tests/ scripts/ --output-format=github
uv run python -m compileall -q src tests
uv run python -m pytest tests -q
```

For startup/run audits:

```bash
uv run python scripts/live_audit_loop.py --cycles 3 --duration 60
```

## Repository Focus

This repository prioritizes backend reliability over visual polish:

- Broker state correctness
- Real-time data proof
- Risk gating
- Position monitoring
- Exit accounting
- Database migrations
- Execution auditability
- Operator notifications
- Testable behavior

## License

MIT License.

## Disclaimer

This project is provided for research and engineering purposes only. Algorithmic trading can lose money quickly. You are responsible for broker permissions, exchange rules, regulatory compliance, taxes, risk controls, and all trading decisions.
