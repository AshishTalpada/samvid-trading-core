import sqlite3

import pandas as pd


def generate_report() -> None:
    db_path = "data/trading.db"
    conn = sqlite3.connect(db_path)

    # Query performance
    query = """
    SELECT
        symbol,
        pattern,
        pnl,
        r_multiple,
        regime,
        recorded_at
    FROM agent_d_trades
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No trades found in database.")
        return

    # Calculate metrics
    total_trades = len(df)
    winning_trades = len(df[df["pnl"] > 0])
    len(df[df["pnl"] <= 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    total_pnl = df["pnl"].sum()
    avg_pnl = df["pnl"].mean()
    avg_r = df["r_multiple"].mean()
    max_win = df["pnl"].max()
    max_loss = df["pnl"].min()

    # System Rating
    rating = "STRONG" if win_rate > 55 and avg_r > 1.5 else "CALIBRATING"

    print("\n" + "=" * 50)
    print("🤖 INSTITUTIONAL TRADING PERFORMANCE REPORT")
    print("=" * 50)
    print(f"Status:            {rating}")
    print(f"Total Trades:      {total_trades:,}")
    print(f"Win Rate:          {win_rate:.2f}%")
    print(f"Total P&L:         ${total_pnl:,.2f}")
    print(f"Avg P&L per Trade: ${avg_pnl:,.2f}")
    print(f"Avg R-Multiple:    {avg_r:.2f}R")
    print("-" * 50)
    print(f"Largest Win:       ${max_win:,.2f}")
    print(f"Largest Loss:      ${max_loss:,.2f}")
    print("=" * 50)

    # Pattern Analysis
    print("\nTop Patterns by Win Rate:")
    pattern_stats = df.groupby("pattern").agg(
        {"pnl": ["count", "sum", "mean"], "r_multiple": "mean"}
    )
    pattern_stats.columns = ["Count", "Total P&L", "Avg P&L", "Avg R"]
    print(pattern_stats.sort_values(by="Count", ascending=False).to_string())
    print("=" * 50 + "\n")


if __name__ == "__main__":
    generate_report()
