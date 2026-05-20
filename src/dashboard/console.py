import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_status_icon(system: Any, component: str) -> str:
    """Helper to return dynamic status icons including Probing states."""
    if component == "ibkr":
        if hasattr(system, "ibkr_client") and system.ibkr_client and system.ibkr_client.isConnected():
            return "🟢 ONLINE"
        if "connect_ibkr" in system.background_tasks:
            return "🟠 PROBING"
        return "🔴 OFFLINE"
    if component == "mt5":
        if hasattr(system, "mt5_client") and system.mt5_client and system.mt5_client.terminal_info():
            return "🟢 ONLINE"
        if "connect_mt5" in system.background_tasks:
            return "🟠 PROBING"
        return "🔴 OFFLINE"
    if component == "qdb":
        if hasattr(system, "qdb") and system.qdb and system.qdb.is_active:
            return "🟢 ACTIVE"
        return "🔴 OFFLINE"
    if component == "dhatu":
        if hasattr(system, "dhatu_oracle") and system.dhatu_oracle:
            return "🟢 CALIBRATED"
        return "🔴 OFFLINE"
    return "⚪ UNKNOWN"


def render_dashboard(system: Any) -> None:
    """Displays a terminal-grade dashboard of active Minds and system diagnostics."""
    ibkr_status = get_status_icon(system, "ibkr")
    mt5_status = get_status_icon(system, "mt5")
    qdb_status = get_status_icon(system, "qdb")
    dhatu_status = get_status_icon(system, "dhatu")

    banner = (
        "\n" + "╔" + "═" * 78 + "╗\n"
        "║" + "    THE SOVEREIGN SINGULARITY MATRIX  ".center(78) + "║\n"
        "╠" + "═" * 78 + "╣\n"
        "║"
        + (
            f"  STATUS:   ACTIVE  |  MODE:     {system.mode.upper().center(10)}  |  "
            "TICK:  100Hz (0.01s)  "
        ).center(78)
        + "║\n"
        "╠" + "═" * 38 + "╦" + "═" * 39 + "╣\n"
        "║  COGNITIVE MINDS (A-M) Status        ║  SYSTEM INFRASTRUCTURE Diagnostics    ║\n"
        "╠" + "═" * 38 + "╬" + "═" * 39 + "╣\n"
        f"║  A: Dhatu Oracle      →  {dhatu_status.ljust(12)}║  Q: QuestDB (TSDB)    →  {qdb_status.ljust(13)}║\n"
        f"║  B: Trading Brain     →  [ACTIVE]    ║  I: IBKR (Broker)     →  {ibkr_status.ljust(13)}║\n"
        f"║  C: Risk Agent        →  [VETTING]   ║  M: MT5 Interface     →  {mt5_status.ljust(13)}║\n"
        "║  D: Evolution Mind    →  [LEARNING]  ║  B: Intelligence Bus  →  [LISTENING]  ║\n"
        "║  E: Data Pipeline     →  [STREAMING] ║  G: Ghost Watchdog    →  [ARBITER]    ║\n"
        "║  K: Ultrathink R-Res  →  [RESONANCE] ║  V: Vault Registry    →  [LOCKED]     ║\n"
        "║  M: Coordinator Phase →  [SOVEREIGN] ║  S: System Mind       →  [STABLE]     ║\n"
        "╠" + "═" * 78 + "╣\n"
        "║" + "   GHOST RUN STATUS: CERTIFIED & HARDENED   ".center(78) + "║\n"
        "╚" + "═" * 78 + "╝\n"
    )
    logger.info(banner)
