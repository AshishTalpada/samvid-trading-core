import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Ensure project root is in path to import DatabaseSecurity
_here = Path(__file__).resolve().parent
_root = str(_here.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from database_security import DatabaseSecurity

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
        # We include more outcomes that represent completed trades
        cursor.execute("""
            SELECT
                instrument, direction, pattern, regime, catalyst_score, dhatu_state, belief_at_entry, pnl_dollars, outcome
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS', 'CLOSED', 'LIQUIDATED', 'EXIT_P1')
        """)

        rows = cursor.fetchall()

        if not rows:
            logger.warning("No completed trades found to train on.")
            return

        extracted_count = 0
        win_count = 0
        loss_count = 0

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for row in rows:
                instrument = row["instrument"]
                direction = row["direction"]
                pattern = row["pattern"]
                regime = row["regime"]
                catalyst = row["catalyst_score"]
                dhatu = row["dhatu_state"]
                belief = row["belief_at_entry"]
                enc_pnl = row["pnl_dollars"]

                pnl = decrypt_pnl(enc_pnl)

                # Determine the correct bias based on trade direction and outcome
                # If PnL > 0, the direction taken was correct.
                # If PnL < 0, the opposite direction was likely correct.
                target = "NEUTRAL"
                if pnl > 0:
                    target = "BULLISH" if str(direction).lower() == "long" else "BEARISH"
                    win_count += 1
                elif pnl < 0:
                    target = "BEARISH" if str(direction).lower() == "long" else "BULLISH"
                    loss_count += 1
                else:
                    target = "NEUTRAL"

                # Skip neutral or tiny PnL for cleaner training
                if abs(pnl) < 0.01:
                    continue

                # Format Context
                context = (
                    f"Instrument: {instrument}\n"
                    f"Regime: {regime}\n"
                    f"Dhatu State: {dhatu}\n"
                    f"Pattern: {pattern}\n"
                    f"Catalyst Score: {catalyst}\n"
                    f"Belief: {belief}\n"
                    f"\nDecision?"
                )

                # OpenAI Chat Format for LLaMA-Factory / Unsloth
                json_record = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Context:\n{context}"},
                        {"role": "assistant", "content": target},
                    ]
                }

                f.write(json.dumps(json_record) + "\n")
                extracted_count += 1

        logger.info(
            f"✅ Successfully extracted {extracted_count} training examples to {OUTPUT_PATH}"
        )
        logger.info(f"Dataset Balance -> Winners: {win_count} | Losers: {loss_count}")
        logger.info("This JSONL file is ready for LoRA fine-tuning.")

    except Exception as e:
        logger.error(f"Error building dataset: {e}")
    finally:
        conn.close()



# ── LOCAL-ONLY SOVEREIGN EXTENSIONS ─────────────────────────────────────


class SLMDataPipeline:
    '''
    Small Language Model (SLM) Data pre-processor.
    Ingests raw Telegram/Twitter financial text, tokenizes, removes stop words,
    and converts to TF-IDF vectors for fast sentiment inference.
    '''
    def __init__(self):
        self.vocab = {}
        self.idf = {}
        self.stop_words = {"the", "is", "at", "which", "on", "and", "a", "of", "to", "in", "for"}
        self.doc_count = 0

    def clean_text(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'http\S+', '', text) # Remove URLs
        text = re.sub(r'[^a-z0-9\s]', '', text) # Remove punctuation
        tokens = text.split()
        return [t for t in tokens if t not in self.stop_words]

    def fit(self, documents: List[str]):
        '''Builds the vocabulary and Inverse Document Frequency (IDF) mapping.'''
        self.doc_count = len(documents)
        df = Counter()

        for doc in documents:
            tokens = set(self.clean_text(doc))
            for t in tokens:
                df[t] += 1

        for word, count in df.items():
            self.vocab[word] = len(self.vocab)
            # IDF = log(N / DF)
            self.idf[word] = np.log(self.doc_count / (count + 1.0))

    def transform(self, text: str) -> np.ndarray:
        '''Converts text into a TF-IDF sparse vector.'''
        vector = np.zeros(len(self.vocab))
        if not self.vocab:
            return vector

        tokens = self.clean_text(text)
        tf = Counter(tokens)

        total_terms = len(tokens) if tokens else 1
        for word, count in tf.items():
            if word in self.vocab:
                idx = self.vocab[word]
                term_frequency = count / total_terms
                vector[idx] = term_frequency * self.idf[word]

        return vector
if __name__ == "__main__":
    build_dataset()
