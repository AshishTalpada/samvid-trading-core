# 📜 Changelog

All notable changes to the **Samvid Trading Core** will be documented in this file.

## [1.1.0-beta] - 2026-05-19
### Added
- Integrated `hmmlearn` for HMM market regime filtering.
- Expanded scanning watchlist to top 25 tickers and aggressively decreased brain scan intervals.
- Loosened opposing confidence thresholds in Agent D to optimize execution throughput.
- Optimized NativeSLM for full GPU-accelerated execution and custom timeout horizons.
- Added a robust trading truth telemetry API and hydrated dashboard frontend views from active backend states.

### Fixed
- **Mathematical Validation**: Corrected time-scaling bug in Monte Carlo outcome simulations, restoring dynamic and accurate `Stat-Prob` calculations.
- **State Reliability**: Integrated custom neutral safety filters to eliminate false-positive `Abhava`/`Viyoga` freezes.
- **Robust Daemon Process**: Fixed Windows process locks (`WinError 5`), closed blank cmd popups, and added a 90s watchdog boot grace period.
- **Idempotent Shutdown**: Ensured single-signal graceful exit sequences to prevent double-signals and SQLite WAL database corruption.
- **Task & Session Integrity**: Addressed timezone-naive datetime conflicts, fixed resource/task leaks in embedding and trade loops, and hardened database position flat states.

### Style
- Cleaned and sorted all source and test imports using Ruff.

## [1.0.1-beta] - 2026-05-17
### Fixed
- Prevented `TaskManager` from filling to 1000 tasks (entropy=1.0 stall).
- Prevented double-shutdown on Ctrl+C (exit code 1 false alarm).
- Raised `data_pipeline` SQLite `busy_timeout` from 5s to 30s to resolve lock issues.
- Resolved numpy JSON serialization bug and `native_slm` setter no-op.
- System-wide JSON sanitization and neural sandbox hardening.
- Restored `self.model_path` assignment for sandbox dispatcher.
- Added missing imports to SLM and sanitized boolean in Ultrathink for perfect JSON quorum.

### Style
- Removed overly verbose banner comments across the project.

## [1.0.0-beta] - 2026-04-28
### Added
- Official **Samvid v1.0-beta** release.
- **Visual Demonstration Suite**: Added `src/demonstration.py` for live terminal simulation.
- **HFT Hardening**: Optimized background task cancellation to ensure 100% clean shutdown.
- **Resilient Embedding Fallback**: Implemented native Python hashing fallback for environments with missing `mmh3` binaries.

### Fixed
- Resolved Windows process-hangs during system exit (asyncio task drain fix).
- Fixed DLL load failures on Windows for `mmh3` dependency.
- Normalized versioning across all core system components.

## [0.9.5-beta] - 2026-04-27
### Added
- Initial public release on GitHub.
- Full "Autonomous Agent Mesh" implementation.
- Dhatu Macro Oracle causation engine.
- Real-time React Telemetry Dashboard.
- Secure Vault integration via OS-level keyring.
- Automated CI/CD workflow with Ruff and Flake8 linting.

### Fixed
- Fixed SVG attribute rendering errors in the Quorum Matrix.
- Resolved WebSocket synchronization latency in high-volatility regimes.

---

### [Historical Versions (Pre-GitHub)]
*Versions v1.0-beta through v1.0-beta were developed as private research iterations.*

## [13.6.0]
- Refined Quorum Matrix consensus logic.
- Integrated QuestDB for high-frequency tick storage.

## [10.0.0]
- First implementation of the Dhatu state-machine.

## [1.0.0]
- Initial MVP: Simple event-driven tick ingestion.
