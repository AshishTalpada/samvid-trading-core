import asyncio
import random


# ANSI Colors for a premium terminal feel
class Colors:
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


async def typewriter_print(text, delay=0.02, color=Colors.END):
    for char in text:
        print(f"{color}{char}{Colors.END}", end="", flush=True)
        await asyncio.sleep(delay)
    print()


async def run_demonstration():
    print(f"\n{Colors.BOLD}{Colors.CYAN} SAMVID TRADING CORE: SOVEREIGN DEMONSTRATION{Colors.END}")
    print(f"{Colors.BLUE}Version: v1.0-beta | Release: 2026-04-28{Colors.END}")
    print("=" * 60)

    await asyncio.sleep(1)

    # 1. Initialization
    await typewriter_print("[-] Initializing Intelligence Mesh...", color=Colors.YELLOW)
    agents = [
        "Agent A (Patterns)",
        "Agent B (Sentiment)",
        "Agent C (Executor)",
        "Agent D (Learning)",
        "Dhatu Oracle",
    ]
    for agent in agents:
        await asyncio.sleep(0.3)
        print(f"    {Colors.GREEN}✓{Colors.END} {agent} synchronized.")

    await asyncio.sleep(0.5)
    print(f"\n{Colors.BOLD}[DHATU ORACLE] SENSING MACRO HORIZONS...{Colors.END}")
    await asyncio.sleep(1)
    regimes = [
        "VRIDDHI (Expansion)",
        "STHITI (Stationary)",
        "KSHAYA (Contraction)",
        "ABHAVA (Void)",
    ]
    detected_regime = random.choice(regimes[:2])  # Let's keep it positive for the demo
    await typewriter_print(f"Detected Regime: {detected_regime}", delay=0.05, color=Colors.MAGENTA)

    await asyncio.sleep(1)

    # 2. Scanning
    print(f"\n{Colors.BOLD}[AGENT A] SCANNING WATCHLIST (SPY, QQQ, NVDA)...{Colors.END}")
    symbols = ["SPY", "QQQ", "NVDA"]
    for sym in symbols:
        await asyncio.sleep(0.8)
        confidence = random.uniform(75, 92)
        print(
            f"    {Colors.CYAN} DISCOVERY:{Colors.END} {sym} matched {Colors.BOLD}BULL_FLAG{Colors.END} ({confidence:.1f}%)"
        )

    await asyncio.sleep(1)

    # 3. Consensus Building
    target = "NVDA"
    print(
        f"\n{Colors.BOLD}[QUORUM] INITIATING CONSENSUS VOTE FOR {target} LONG ENTRY...{Colors.END}"
    )
    await asyncio.sleep(1)

    votes = [
        ("Agent A", "YES", 0.92, "High-confidence Bull Flag breakout detected."),
        ("Agent B", "YES", 0.78, "Positive sentiment sentiment in tech sector."),
        ("Dhatu Oracle", "YES", 0.85, "Macro environment supports expansion."),
        ("Agent D", "YES", 0.70, "Historical expectancy matrix positive for this setup."),
        ("Risk Guard", "YES", 1.00, "Position sizing within 0.5% risk limits."),
    ]

    for agent, vote, conf, reason in votes:
        await asyncio.sleep(0.5)
        print(
            f"    {Colors.BOLD}{agent}:{Colors.END} [{Colors.GREEN}{vote}{Colors.END}] | Confidence: {conf:.2f} | {Colors.BLUE}{reason}{Colors.END}"
        )

    await asyncio.sleep(1)
    print(f"\n{Colors.BOLD}{Colors.YELLOW} CONSENSUS REACHED: 100% APPROVAL{Colors.END}")
    print(f"{Colors.GREEN}ACTION: EXECUTING LIMIT ORDER FOR {target} @ MARKET...{Colors.END}")

    await asyncio.sleep(1.5)

    # 4. Execution Telemetry
    print(f"\n{Colors.BOLD}[AGENT C] EXECUTION TELEMETRY{Colors.END}")
    print(f"    Broker: {Colors.CYAN}IBKR (Paper){Colors.END}")
    print(f"    Status: {Colors.GREEN}FILLED{Colors.END}")
    print(f"    Position ID: {Colors.BLUE}TRD-X882-SAMVID{Colors.END}")
    print(
        f"    Exit Intelligence: {Colors.YELLOW}ACTIVE (Monitoring Posterior Beliefs...){Colors.END}"
    )

    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}{Colors.MAGENTA}DEMONSTRATION COMPLETE.{Colors.END}")
    print(f"{Colors.BOLD}Samvid Trading Core is now ready for deployment.{Colors.END}")


if __name__ == "__main__":
    try:
        asyncio.run(run_demonstration())
    except KeyboardInterrupt:
        print("\nShutdown.")
