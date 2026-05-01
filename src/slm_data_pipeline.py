import sqlite3
import json
import logging
from pathlib import Path
import sys
import os

# Ensure project root is in path to import DatabaseSecurity
_here = Path(__file__).resolve().parent
_root = str(_here.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.database_security import DatabaseSecurity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SLM_DataPipeline")

DB_PATH = Path("data/trading.db")
OUTPUT_PATH = Path("data/slm_training_data.jsonl")

SYSTEM_PROMPT = "You are Sovereign-SLM, an elite quantitative strategist. Analyze the market context and output exactly one word: BULLISH, BEARISH, or NEUTRAL."

def decrypt_pnl(raw_pnl: str) -> float:
    if raw_pnl is None:
        return 0.0
    try:
        if isinstance(raw_pnl, str) and raw_pnl.startswith("gAAAAA"):
            return DatabaseSecurity.decrypt_float(raw_pnl)
        return float(raw_pnl)
    except Exception:
        return 0.0

def build_dataset():
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return

    logger.info("Extracting historical trades for SLM Fine-Tuning...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                instrument, direction, pattern, regime, catalyst_score, dhatu_state, belief_at_entry, pnl_dollars
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS')
        """)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"SQL Error: {e}. Are you sure the trades table is fully populated?")
        return
    finally:
        conn.close()

    if not rows:
        logger.warning("No completed trades found to train on.")
        return

    extracted_count = 0
    win_count = 0
    loss_count = 0

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            # Safely decrypt PnL
            pnl = decrypt_pnl(row["pnl_dollars"])
            
            direction = str(row["direction"]).lower()
            
            # Determine target Label
            if pnl > 0:
                target = "BULLISH" if direction == "long" else "BEARISH"
                win_count += 1
            else:
                # If the trade lost money, we train the SLM to remain NEUTRAL on this setup
                target = "NEUTRAL"
                loss_count += 1

            # Format Context
            context = (
                f"Instrument: {row['instrument']}\n"
                f"Regime: {row['regime']}\n"
                f"Dhatu State: {row['dhatu_state']}\n"
                f"Pattern: {row['pattern']}\n"
                f"Catalyst Score: {row['catalyst_score']}\n"
                f"Belief: {row['belief_at_entry']}\n"
                f"\nDecision?"
            )

            # OpenAI Chat Format for LLaMA-Factory / Unsloth
            json_record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context:\n{context}"},
                    {"role": "assistant", "content": target}
                ]
            }

            f.write(json.dumps(json_record) + "\n")
            extracted_count += 1

    logger.info(f"✅ Successfully extracted {extracted_count} training examples to {OUTPUT_PATH}")
    logger.info(f"Dataset Balance -> Winners (Directional): {win_count} | Losers (Neutralized): {loss_count}")
    logger.info("This JSONL file is ready for LoRA fine-tuning via HuggingFace or Unsloth.")

if __name__ == "__main__":
    build_dataset()
