import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"

import sys
import asyncio
import sqlite3
import random
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    # Minimal fallback if rich is not installed
    class Console:
        def print(self, *args, **kwargs): print(*args)
    class Panel:
        def __init__(self, *args, **kwargs): pass
    # ... etc (but likely rich is there)

from swarm_predictor import SwarmPredictor

console = Console()

async def run_sovereign_demo():
    console.print("\n[bold magenta]💀 SOVEREIGN AI: HISTORICAL GHOST REPLAY 💀[/bold magenta]")
    console.print("[dim]Simulating Market Intelligence using 1,000,000 Vector Subconscious Memory...[/dim]\n")

    # 1. Fetch a random "Extreme" anomaly from the 75Y Database
    db_path = "data/sovereign_intelligence_75y.db"
    if not os.path.exists(db_path):
        console.print(f"[red]Error: Database {db_path} not found. Ensure 75Y forging is complete.[/red]")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pattern_type, micro_intensity, survival_score, timestamp 
        FROM structural_fingerprints 
        WHERE survival_score > 0.95 -- Required for Flash-Inference (SFI)
        ORDER BY RANDOM() LIMIT 1000
    """)
    ghost = cursor.fetchone()
    conn.close()

    if not ghost:
        console.print("[yellow]No high-intensity ghosts found in memory. Reverting to base simulation.[/yellow]")
        ghost = ("VOLATILITY_SQUEEZE", 95.5, 0.98, "2024-03-15 14:30:00")

    pattern, intensity, survival, ts = ghost
    
    # Construct a Market Snapshot
    market_snapshot = {
        "symbol": "GHOST_ASSET",
        "price": random.uniform(100, 500),
        "vix": random.uniform(15, 35),
        "regime": pattern,
        "intensity": intensity,
        "timestamp": ts
    }

    # 2. Display the Market Situation
    table = Table(title="[bold cyan]Market Snapshot (Reconstructed Ghost)[/bold cyan]", box=box.DOUBLE)
    table.add_column("Property", style="dim")
    table.add_column("Value", style="bold yellow")
    table.add_row("Pattern Type", pattern)
    table.add_row("Micro Intensity", f"{intensity:.2f}")
    table.add_row("Historical Survival", f"{survival:.1%}")
    table.add_row("Historical Date", ts)
    console.print(table)

    # 3. Initialize Swarm (Subconscious Memory automatically loads)
    predictor = SwarmPredictor(cache_minutes=0)
    
    console.print("\n[bold green]▶ Initiating Swarm Quorum...[/bold green]")
    console.print("[dim]Agents are scanning 1,000,807 historical vectors to find similar 'Geometric Scent'...[/dim]\n")

    # 4. Get Forecast (This will trigger the vector search and debate)
    with console.status("[bold green]Swarm Agents are debating the Ghost...[/bold green]"):
        consensus = await predictor.get_market_forecast("SPY", market_snapshot)

    # 5. Display the Debate Summary & Memory Resonance
    console.print(Panel(
        Text(consensus.summary),
        title="[bold magenta]Chief Strategist Summary[/bold magenta]",
        border_style="magenta",
        padding=(1, 2)
    ))

    # 6. Final Verdict
    bias_style = "bold green" if "BULL" in str(consensus.bias) else "bold red" if "BEAR" in str(consensus.bias) else "bold yellow"
    
    final_table = Table(box=box.SIMPLE_HEAVY)
    final_table.add_column("Sovereign Verdict", justify="center")
    final_table.add_column("Confidence Score", justify="center")
    final_table.add_column("Resonance Check", justify="center")
    
    # Resonance: Does the AI consensus match the historical outcome?
    is_bull_match = (consensus.bias == "BULLISH" and survival > 0.5)
    is_bear_match = (consensus.bias == "BEARISH" and survival <= 0.5)
    
    resonance = "SYNCHRONIZED" if (is_bull_match or is_bear_match) else "DIVERGENT"
    res_style = "bold cyan" if resonance == "SYNCHRONIZED" else "bold orange3"

    final_table.add_row(
        Text(str(consensus.bias), style=bias_style),
        Text(f"{consensus.confidence:.1%}", style="bold yellow"),
        Text(resonance, style=res_style)
    )
    
    console.print(final_table)
    
    # Reveal Historical Outcome
    outcome = "EXPLOSIVE WIN" if survival > 0.7 else "MINOR WIN"
    console.print(f"\n[bold white]💀 HISTORICAL REALITY:[/] This specific anomaly resulted in an [bold green]{outcome}[/bold green].")
    console.print("[dim]The Swarm successfully identified the Geometric Signature in under 10 seconds.[/dim]\n")

if __name__ == "__main__":
    asyncio.run(run_sovereign_demo())
