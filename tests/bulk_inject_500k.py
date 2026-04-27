import random
import sqlite3
import time


def bulk_injection(target=500000) -> None:
    db_path = "data/trading_stress.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")

    # Get current count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM agent_d_trades")
    current = cursor.fetchone()[0]

    remaining = target - current
    if remaining <= 0:
        print("Target already reached.")
        return

    print(f"🚀 GIGADATA INJECTION: Filling {remaining:,} trades into Stored Memory...")

    batch_size = 50000
    symbols = [f"GIGA-{i}" for i in range(1000)]
    patterns = ["MACD_DIVERGENCE", "BULL_FLAG", "GAP_FILL", "RSI_OVERSOLD"]

    start_time = time.time()

    for i in range(0, remaining, batch_size):
        this_batch = min(batch_size, remaining - i)
        rows = []
        for _ in range(this_batch):
            is_win = random.random() < 0.62  # Calibrated win rate
            pnl = random.uniform(100, 500) if is_win else random.uniform(-200, -50)
            rows.append(
                (
                    random.choice(symbols),
                    random.choice(patterns),
                    "WIN" if is_win else "LOSS",
                    pnl / 100.0,
                    pnl,
                    "BULL",
                    "RTH",
                    0.1,
                )
            )

        conn.executemany(
            "INSERT INTO agent_d_trades (symbol, pattern, outcome, r_multiple, pnl, regime, session, hold_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        print(f"✔️ Batch {i + this_batch:,}/{remaining:,} injected.")

    duration = time.time() - start_time
    print(f"🏁 GIGADATA COMPLETE: {remaining:,} trades injected in {duration:.1f}s")
    conn.close()


if __name__ == "__main__":
    bulk_injection(500000)
