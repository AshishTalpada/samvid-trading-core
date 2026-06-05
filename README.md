# Samvid Trading Core

[![Main Build](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/main.yml/badge.svg)](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/main.yml)
[![Quality](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/quality.yml/badge.svg)](https://github.com/AshishTalpada/samvid-trading-core/actions/workflows/quality.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![IBKR Paper](https://img.shields.io/badge/IBKR-Paper%20Execution-green)
![TradingView Quotes](https://img.shields.io/badge/TradingView-Realtime%20Quote%20Lane-orange)
![Telegram Alerts](https://img.shields.io/badge/Telegram-Operator%20Alerts-2CA5E0)
![License](https://img.shields.io/badge/License-MIT-black)

Samvid Trading Core is a backend-first AI trading system for Interactive Brokers paper execution, real-time market-data monitoring, automated trade routing, risk controls, broker reconciliation, learning loops, and Telegram operator alerts.

The system is built around one practical idea: a trading engine should not just find signals. It should prove that data is fresh, explain why an order was accepted or rejected, route broker-paper orders safely, monitor open positions, reconcile against broker truth, learn from exits, and notify the operator with useful context.

> This is trading research and engineering software, not financial advice. Use `TRADING_MODE=ibkr_paper` for broker-connected paper execution. Live trading requires independent validation, broker permissions, compliance review, and capital-risk controls.

## Search Keywords

AI trading system, algorithmic trading bot, Interactive Brokers trading bot, IBKR paper trading bot, automated trading backend, TradingView quote streamer, Python quantitative trading platform, multi-agent trading AI, Telegram trading alerts, broker reconciliation engine, real-time market data pipeline, risk-managed trading system, paper trading automation, execution audit framework, post-trade learning engine.

## What It Does

| System layer | What Samvid does |
| --- | --- |
| Market data | Combines OHLCV ingestion, TradingView quote streaming, broker snapshots, VIX/macro context, and news/oracle signals. |
| Decision engine | Detects setups, evaluates regime, checks freshness, runs quorum logic, applies friction and risk gates, and records rejections. |
| Execution | Routes accepted orders to IBKR paper mode, captures broker order IDs, stores order state, and blocks stale-data entries. |
| Position management | Tracks open positions, partial exits, stop/target logic, exit method, net PnL, and R multiple. |
| Reconciliation | Compares local state against IBKR broker state to catch stale, missing, orphaned, rejected, cancelled, or filled orders. |
| Learning | Feeds `trade.exit` events into calibration, alpha-health, expectancy, strategy memory, and future gating. |
| Operator UX | Sends Telegram startup, execution, rejection, exit, DMS, and runtime-health alerts with actionable details. |
| Reliability | Uses watchdogs, runtime health snapshots, startup validation, restart audits, and CI checks to surface failures quickly. |

## Current Operating Modes

| Mode | Broker connection | Orders sent | Intended use |
| --- | --- | --- | --- |
| `paper` | No IBKR broker connection | Internal simulated paper orders only | Safe local smoke tests |
| `ibkr_paper` | IBKR TWS / Gateway paper account | Real paper-account orders | Primary operational mode |
| `live` | IBKR live account when explicitly allowed | Real live orders | Disabled unless `ALLOW_FORCE_LIVE=1` |

Recommended broker-paper launch:

```powershell
$env:TRADING_MODE = "ibkr_paper"
$env:ALLOW_FORCE_LIVE = "0"
$env:SOVEREIGN_TV_QUOTES_ENABLED = "1"
$env:SOVEREIGN_IBKR_HFT_ENABLED = "0"
uv run python src/main.py
```

This keeps IBKR focused on order execution while the TradingView quote streamer supplies the faster quote lane.

## System Status Matrix

| Component | Status | Why it matters |
| --- | --- | --- |
| IBKR paper execution | Supported | Routes broker-paper orders through TWS/Gateway and verifies broker state. |
| TradingView quote lane | Supported | Provides fast quote updates for entry proof and market awareness. |
| Telegram alerts | Supported | Keeps the operator informed without watching the terminal all day. |
| Data pipeline | Supported | Maintains candles, macro context, news context, and market snapshots. |
| Dhatu Oracle | Supported | Converts news/macro context into risk-state and freeze signals. |
| Native SLM | Optional/fallback | Uses deterministic fallback if the native GGUF runtime is unavailable. |
| QuestDB | Optional | High-throughput path when available; SQLite remains the durable local record. |
| MT5 | Optional | Runtime-aware optional broker path when credentials exist. |
| Live mode | Guarded | Blocked unless explicitly authorized with `ALLOW_FORCE_LIVE=1`. |

## Architecture Flowchart

```text
                  MARKET + CONTEXT INPUTS
  ----------------------------------------------------------------
  TradingView quotes | OHLCV pipeline | IBKR snapshots | News/Macro
            |              |               |              |
            +--------------+---------------+--------------+
                           |
                           v
                    Shared Event Bus
                           |
                           v
                    TradingBrain
        regime detection | scan loop | position monitor
                           |
                           v
                   TradingCoordinator
      freshness proof | risk gates | quorum | friction veto
                           |
              +------------+------------+
              |                         |
              v                         v
        IBKR paper order          Decision rejection
              |                         |
              v                         v
     Broker order id / status     Rejection evidence
              |                         |
              +------------+------------+
                           |
                           v
              SQLite evidence + reconciliation
                           |
              +------------+------------+
              |                         |
              v                         v
        Telegram alerts       Post-trade learning
```

## Data Pipeline

```text
Raw market sources
  |
  +-- TradingView quote streamer
  |     -> tick/quote events
  |     -> fast entry proof
  |     -> candle.batch / hft-style bus updates
  |
  +-- OHLCV provider lane
  |     -> 1m / 5m / 15m bars
  |     -> continuity backfill
  |     -> after-hours compact sync
  |
  +-- News and macro lane
  |     -> Reuters/Finnhub/OpenBB-style context
  |     -> VIX and market-regime context
  |     -> Dhatu risk-state synthesis
  |
  +-- Broker state lane
        -> IBKR account, positions, order status
        -> reconciliation and orphan detection
```

## Automated Trade Lifecycle

| Phase | What happens |
| --- | --- |
| Discovery | Brain scans the watchlist and receives candle/quote/news events. |
| Setup detection | Pattern logic identifies a candidate entry with price, stop, target, and confidence. |
| Data proof | Coordinator requires fresh bars or realtime quote proof before broker-paper execution. |
| Risk and friction | System checks R:R, fees, spread/slippage assumptions, budget, loss locks, and oracle freeze. |
| Quorum | Agent votes and risk gates decide whether the candidate can become an order. |
| Execution | Accepted trades route to IBKR paper and return a broker order id. |
| Notification | Telegram receives mode, broker, order id, method, pattern, qty, stop, target, confidence, and reason. |
| Monitoring | Position monitor tracks open risk, partials, stop/target logic, and market state. |
| Reconciliation | IBKR state is compared against local records to prevent unmanaged stale positions. |
| Learning | Exit results update calibration, expectancy, alpha-health, and future decision quality. |

## Learning Loop

```text
Trade exit
   |
   v
Net PnL + R multiple + exit method + strategy metadata
   |
   v
Agent D / live learning / calibration matrix
   |
   v
Alpha health, pattern expectancy, regime/session memory
   |
   v
Future risk gates and strategy promotion decisions
```

The system does not treat a trade as just a row in a database. It turns exits into feedback: which setup fired, what regime it happened in, how the exit resolved, whether the edge is warming up or decaying, and whether future trades should be allowed, reduced, or blocked.

## Operator Alerts

| Alert type | Trigger | Includes |
| --- | --- | --- |
| Startup | System online | Mode, IBKR, MT5, Dhatu, OpenBB, Native SLM, startup latency. |
| Execution | Broker accepts order | Mode, broker, order id, side/method, pattern, setup class, prices, quantity, confidence. |
| Rejection | Coordinator or broker veto | Symbol, reason, proposal id, and rejection context. |
| Exit | Position closes | Strategy, pattern, exit method, price source, net PnL, R multiple, session PnL. |
| Recovery lock | Loss streak or audit state | Why entries are disabled and when review/reset is expected. |
| DMS | Dead Man Switch status | Execution online/offline state and emergency monitor state. |
| Health | Runtime degraded | Broker connectivity, feed delay, fallback state, or stale heartbeat. |

## Why This Is More Than a Toy Bot

| Capability | Basic bot | Samvid Trading Core |
| --- | --- | --- |
| Entry logic | Buy/sell when indicator crosses | Pattern detection plus regime, oracle, quorum, freshness, and risk gates. |
| Data freshness | Often assumed | Explicitly checked before broker-paper entries. |
| Broker routing | Fire-and-forget order | IBKR paper execution with order id capture and reconciliation. |
| Notifications | Generic fill messages | Context-rich Telegram alerts with method, pattern, order id, risk, and reason. |
| Risk control | Static stop loss | Drawdown, loss-streak locks, oracle freeze, friction veto, and recovery/audit states. |
| Learning | Manual review | Automated `trade.exit` feedback into expectancy and alpha-health logic. |
| Observability | Terminal logs only | Logs, health snapshots, Telegram, audit summaries, and CI validation. |
| Restart behavior | Unknown | Startup validation, watchdogs, PID guards, and restart audit tooling. |

## Repository Map

| Path | Purpose |
| --- | --- |
| `src/main.py` | Startup, mode safety, broker connections, watchdogs, metrics, notifications. |
| `src/brain.py` | Main trading state machine, scan loop, oracle gate, and runtime coordination. |
| `src/coordinator.py` | Entry quorum, risk gates, broker routing, execution alerts, rejection evidence. |
| `src/agent_c_ibkr.py` | IBKR order placement, account sync, active order audit, reconciliation support. |
| `src/brain_position.py` | Position monitoring, exit intelligence, final PnL accounting, exit alerts. |
| `src/brain_reconcile.py` | Broker/database reconciliation and stale trade handling. |
| `src/data_pipeline.py` | OHLCV, market data, news, macro, and fallback ingestion. |
| `src/tv_quote_streamer.py` | TradingView realtime quote streaming. |
| `src/telegram_alerts.py` | Telegram alert transport, sanitization, and rate limiting. |
| `src/brain_health.py` | Runtime health and throttled execution status reports. |
| `scripts/live_audit_loop.py` | Kill/restart audit runner and log summarizer. |
| `tests/` | Risk, execution, startup, reconciliation, health, and integration coverage. |

## Verification

Run the same checks used before pushing:

```bash
uv run ruff check src/ tests/ scripts/ --output-format=github
uv run python -m compileall -q src tests scripts
uv run python -m pytest tests -q
```

Run startup validation:

```bash
uv run python scripts/startup_validation.py
```

Run a short restart audit:

```bash
uv run python scripts/live_audit_loop.py --cycles 1 --duration 35
```

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `TRADING_MODE` | `paper`, `ibkr_paper`, or `live`. |
| `ALLOW_FORCE_LIVE` | Must be `1` before live mode can run. |
| `SOVEREIGN_TV_QUOTES_ENABLED` | Enables the TradingView quote lane. |
| `SOVEREIGN_IBKR_HFT_ENABLED` | Enables IBKR as tick fallback, usually off when TV quotes are active. |
| `SOVEREIGN_ENTRY_DATA_PROOF_MAX_AGE_SEC` | Max age for entry freshness proof. |
| `SOVEREIGN_PAPER_EXPLORATION` | Allows tiny broker-paper learning orders on high-quality near misses. |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token. |
| `TELEGRAM_CHAT_ID` | Telegram destination chat id. |
| `IB_HOST` | IBKR host, usually `127.0.0.1`. |
| `IB_PORT` | IBKR paper port, usually `7497`. |

## Honest Production Position

Samvid Trading Core is a serious solo trading-system backend with broker-paper execution, automated risk gating, reconciliation, observability, and post-trade learning. It is stronger than a simple retail bot because it treats execution, logs, state, failures, and learning as first-class parts of the system.

It is not yet a hedge-fund production platform. To move closer to that level, it needs longer live-market IBKR paper soak tests, verified positive expectancy after costs, stronger feed redundancy, richer external monitoring, and repeated reconciliation reports showing no unexplained broker drift.

## License

MIT License.

## Disclaimer

Trading can lose money quickly. You are responsible for broker permissions, exchange rules, taxes, compliance, strategy validation, risk controls, and all decisions made with this software.
