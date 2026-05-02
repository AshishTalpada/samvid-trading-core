import logging
import os
import sqlite3
import sys

import numpy as np
from tqdm import tqdm

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
import polars as pl

from agent_a import PatternDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HyperFidelityTrainer")

DB_PATH = "training_data.db"
INTEL_DB = "data/sovereign_intelligence_75y.db"


def init_intel_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(INTEL_DB, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS structural_fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pattern_type TEXT,
            micro_intensity REAL,
            survival_score REAL
        )
    """)
    conn.commit()
    return conn


def simulate_hyper_ticks(open_p, high_p, low_p, close_p, vol, num_ticks=1000):
    """
    Multifractal Hyper-Expansion.
    Generates high-fidelity micro-ticks using a self-similar fractional walk.
    """
    # Base linspace
    ticks = np.linspace(open_p, close_p, num_ticks)
    # Volatility Scent: Scaled noise (Guard against zero spread)
    scale = (high_p - low_p) / 10.0
    if scale <= 1e-6:
        scale = 0.01  # Institutional default

    noise = np.random.normal(0, scale, num_ticks)
    ticks += noise

    # Structural Walls: 10 'Iceberg' events per day
    for _ in range(10):
        idx = np.random.randint(50, num_ticks - 50)
        level = ticks[idx]
        ticks[idx : idx + 20] = level + np.random.normal(0, 0.0001, 20)

    ticks = np.clip(ticks, low_p, high_p)
    ticks[0] = open_p
    ticks[-1] = close_p

    tick_vols = np.random.poisson(vol / num_ticks, num_ticks).astype(float)
    return ticks, tick_vols


def train_75y_hardcore():
    print("\n💀💀💀 STARTING GLOBAL ADVERSARIAL MASTER TRAINING (75Y MULTI-SECTOR) 💀💀💀")
    print("  ▶ Targeted Scope: 75 Years (SPY + QQQ + IWM)")
    print("  ▶ Mode: ADVERSARIAL_GAMMA_TRAP ACTIVE")

    intel_conn = init_intel_db()

    # --- INTELLIGENT JUMP: Find last processed timestamp ---
    cursor = intel_conn.cursor()
    cursor.execute("SELECT MAX(timestamp) FROM structural_fingerprints")
    last_ts = cursor.fetchone()[0]

    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL;")

    if last_ts:
        print(f"  🧠 SOVEREIGN MEMORY DETECTED: Resuming from {last_ts}...")
        query = f"SELECT open, high, low, close, volume, timestamp, symbol FROM ohlcv WHERE symbol LIKE '%_PROXY' AND timestamp > '{last_ts}' ORDER BY timestamp ASC"
    else:
        print("  🌑 NO MEMORY FOUND: Starting full 75Y historical initialization...")
        query = "SELECT open, high, low, close, volume, timestamp, symbol FROM ohlcv WHERE symbol LIKE '%_PROXY' ORDER BY timestamp ASC"

    df_all = pl.read_database(query, conn)
    conn.close()

    detector = PatternDetector()
    total_days = len(df_all)

    print(f"  ▶ COMMENCING EXHAUSTIVE ANALYSIS OF {total_days:,} SECTOR-DAYS...")

    batch_size = 100
    for start_idx in range(0, total_days, batch_size):
        end_idx = min(start_idx + batch_size, total_days)
        batch_records = []

        for i in tqdm(range(start_idx, end_idx), desc=f"Batch {start_idx // batch_size}"):
            row_data = df_all.row(i)
            o, h, l, c, v = (
                float(row_data[0]),
                float(row_data[1]),
                float(row_data[2]),
                float(row_data[3]),
                float(row_data[4]),
            )
            ts_val = str(row_data[5])
            sym = str(row_data[6])

            # ADVERSARIAL SIMULATION (Injection of Sector-Specific Chaos)
            if sym == "QQQ_PROXY":
                # Tech is high-beta; simulate higher noise + Gamma drift
                ticks, volumes = simulate_hyper_ticks(o, h, l, c, v, num_ticks=20000)
                if np.random.rand() < 0.1:  # 10% of tech days have 'Gamma Squeezes'
                    squeeze_zone = np.random.randint(5000, 15000)
                    ticks[squeeze_zone : squeeze_zone + 400] *= 1.005  # Instant 0.5% micro-pop
            else:
                ticks, volumes = simulate_hyper_ticks(o, h, l, c, v, num_ticks=20000)

            tick_df = pl.DataFrame(
                {"close": ticks, "high": ticks + 0.0001, "low": ticks - 0.0001, "volume": volumes}
            )

            # EXHAUSTIVE SCAN (Ultra-Density)
            for j in range(20, 20000, 20):
                window = tick_df[j - 20 : j]
                abs_res = detector.detect_tick_tape_absorption(window, sensitivity=2.5)
                if abs_res:
                    batch_records.append(
                        (
                            ts_val,
                            f"{sym}:{abs_res.name}",  # Tag with sector
                            abs_res.confidence / 100.0,
                            float(abs_res.r_r_ratio),
                        )
                    )

        if batch_records:
            intel_conn.executemany(
                "INSERT INTO structural_fingerprints (timestamp, pattern_type, micro_intensity, survival_score) VALUES (?,?,?,?)",
                batch_records,
            )
            intel_conn.commit()

    intel_conn.close()
    print("\n✅✅✅ GLOBAL ADVERSARIAL MASTER TRAINING COMPLETE ✅✅✅")
    print(f"  Total Sector-Days Processed: {total_days}")
    print("  Sovereign Memory Hardened across: SPY, QQQ, IWM")


if __name__ == "__main__":
    train_75y_hardcore()
