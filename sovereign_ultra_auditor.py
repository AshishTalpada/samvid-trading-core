import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"

import sys
import asyncio
import sqlite3
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich import box
except ImportError:
    print("Error: 'rich' library required.")
    sys.exit(1)

from swarm_predictor import SwarmPredictor

console = Console()

async def run_ultra_auditor(sample_count=100000):
    console.print(f"\n[bold green]🛡️ SOVEREIGN ULTRA-AUDITOR: {sample_count:,} GHOSTS[/bold green]")
    
    db_path = "data/sovereign_intelligence_75y.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Pull ONLY the highest-fidelity anomalies (>0.9 or <0.1 survival)
    cursor.execute("""
        SELECT pattern_type, micro_intensity, survival_score 
        FROM structural_fingerprints 
        WHERE survival_score > 0.95 OR survival_score < 0.05
        LIMIT ?
    """, (sample_count,))
    samples = cursor.fetchall()
    conn.close()

    predictor = SwarmPredictor(cache_minutes=0)
    collection = predictor._memory.collection
    
    start_time = time.time()
    correct = 0
    total = 0
    
    BATCH_SIZE = 1000 
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]High-Fidelity Neural Audit...", total=len(samples))
        
        for i in range(0, len(samples), BATCH_SIZE):
            batch = samples[i:i+BATCH_SIZE]
            # Construct Query texts exactly as they appear in the forged memory
            query_texts = [
                f"Historical Event. Pattern: {s[0]}. Volatility Spike: {s[1]:.2f}. Win-Rate Probability: {s[2]:.2f}."
                for s in batch
            ]
            
            # --- BATCH VECTOR SEARCH (Native CPU Parallelism) ---
            results = await asyncio.to_thread(
                collection.query,
                query_texts=query_texts,
                n_results=1,
                include=['metadatas']
            )
            
            for idx, res_meta in enumerate(results['metadatas']):
                if not res_meta: continue
                
                # Check Resonance: Hist Bias == Found Bias
                hist_bias = "BULLISH" if batch[idx][2] > 0.5 else "BEARISH"
                vector_bias = res_meta[0].get("bias", "NEUTRAL")
                
                if hist_bias == vector_bias:
                    correct += 1
                total += 1
            
            progress.update(task, advance=len(batch))

    end_time = time.time()
    duration = end_time - start_time
    accuracy = (correct / total) * 100 if total > 0 else 0
    
    summary = Table(title="[bold green]Final Sovereign Integrity Report[/bold green]", box=box.ROUNDED)
    summary.add_column("Property", style="dim")
    summary.add_column("Metric", style="bold yellow")
    
    summary.add_row("Total Samples Audited", f"{total:,}")
    summary.add_row("Vector Resonance (Accuracy)", f"{accuracy:.2f}%")
    summary.add_row("Audit Latency", f"{duration:.2f}s")
    summary.add_row("Velocity", f"{total/duration:,.1f} Ghost/Sec")
    
    console.print("\n", summary)
    
    if accuracy > 95:
        console.print(f"\n[bold green]✅ SYSTEM VERIFIED: {accuracy:.2f}% Resonance reached. Sovereignty status: ULTIMATE.[/bold green]\n")
    else:
        console.print(f"\n[bold red]❌ FAULT DETECTED: Resonance only {accuracy:.2f}%. Check forge integrity.[/bold red]\n")

if __name__ == "__main__":
    asyncio.run(run_ultra_auditor(1000))
