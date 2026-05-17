# 📜 Changelog

All notable changes to the **Samvid Trading Core** will be documented in this file.

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
