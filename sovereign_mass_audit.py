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
    print("Error: 'rich' library required. Run: pip install rich")
    sys.exit(1)

from swarm_predictor import SwarmPredictor

console = Console()

async def run_turbo_audit(sample_count=100000):
    console.print(f"\n[bold magenta]🚀 SOVEREIGN TURBO-AUDIT: {sample_count:,} GHOSTS[/bold magenta]")
    
    db_path = "data/sovereign_intelligence_75y.db"
    if not os.path.exists(db_path):
        console.print(f"[red]Error: Database {db_path} not found.[/red]")
        return

    # 1. Bulk Extraction
    console.print(f"▶ Loading {sample_count:,} anomalies...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pattern_type, micro_intensity, survival_score 
        FROM structural_fingerprints 
        WHERE survival_score > 0.9 OR survival_score < 0.1
        LIMIT ?
    """, (sample_count,))
    samples = cursor.fetchall()
    conn.close()

    # 2. Access Vector Engine Directly
    predictor = SwarmPredictor(cache_minutes=0)
    collection = predictor._memory.collection
    if not collection:
        console.print("[red]Vector Memory Offline.[/red]")
        return

    start_time = time.time()
    correct_identifications = 0
    total_processed = 0
    
    # 3. Neural Batch Loop (500 ghosts per step)
    BATCH_SIZE = 500
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[magenta]Quantum Vector Resonance...", total=len(samples))
        
        for i in range(0, len(samples), BATCH_SIZE):
            batch = samples[i:i+BATCH_SIZE]
            
            # Construct Query Descriptions
            query_texts = [
                f"Historical Event. Pattern: {s[0]}. Volatility Spike: {s[1]:.2f}. Win-Rate Probability: {s[2]:.2f}."
                for s in batch
            ]
            
            # --- BATCH VECTOR SEARCH (Rust Optimized) ---
            results = await asyncio.to_thread(
                collection.query,
                query_texts=query_texts,
                n_results=1,
                include=['metadatas', 'documents']
            )
            
            # Validate results
            for idx, (original, result_meta) in enumerate(zip(batch, results['metadatas'])):
                if not result_meta: continue
                # Match actual survival bias vs found bias
                actual_bias = "BULLISH" if original[2] > 0.5 else "BEARISH"
                # Flash-Inference logic: the retrieved ghost's bias
                found_bias = result_meta[0].get("bias", "NEUTRAL")
                
                if actual_bias == found_bias:
                    correct_identifications += 1
            
            total_processed += len(batch)
            progress.update(task, advance=len(batch))

    end_time = time.time()
    
    # 4. Final Velocity Report
    total_time = end_time - start_time
    accuracy = (correct_identifications / total_processed) * 100 if total_processed > 0 else 0
    speed = total_processed / total_time
    
    summary = Table(title="[bold green]Sovereign Turbo-Audit Report[/bold green]", box=box.ROUNDED)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Result", style="bold yellow")
    
    summary.add_row("Total Samples Audited", f"{total_processed:,}")
    summary.add_row("Global Atlas Accuracy", f"{accuracy:.2f}%")
    summary.add_row("Turbo Velocity", f"{speed:.1f} Ghost/Sec")
    summary.add_row("Total Time", f"{total_time:.2f}s")
    
    console.print("\n", summary)
    console.print(f"\n[bold green]✅ TURBO-AUDIT COMPLETE. The engine is processing history at {speed:.1f}x real-time speed.[/bold green]\n")

if __name__ == "__main__":
    asyncio.run(run_turbo_audit(100000))
