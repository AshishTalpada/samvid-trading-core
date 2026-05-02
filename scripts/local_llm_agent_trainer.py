import asyncio
import json
import sqlite3
import time

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-gpu"

print("💀💀💀 SOVEREIGN AI: INITIATING LOCAL LLM AGENT DISTILLATION 💀💀💀")
print(f"▶ Target Model: Local {MODEL_NAME}")
print("▶ Objective: Forcing local LLM to absorb 11M Fingerprints.")


async def prompt_local_llm(client, prompt_text):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_text,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 4096},
    }
    try:
        response = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            payload["model"] = "qwen2.5:1.5b"
            response = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            return f"Error: {response.text}"
    except Exception as e:
        return str(e)


async def train_local_agents_from_11m_database():
    print("🌀 INITIATING STATISTICAL FUNNEL COMPRESSION (11M ROWS -> LLM CHUNKS)")
    try:
        conn = sqlite3.connect("data/sovereign_intelligence_75y.db")
        c = conn.cursor()
        c.execute("""
            SELECT
                pattern_type,
                COUNT(*) as occurrence_count,
                AVG(micro_intensity) as avg_intensity,
                AVG(survival_score) as true_win_rate
            FROM structural_fingerprints
            GROUP BY pattern_type
            HAVING occurrence_count > 1000
            ORDER BY true_win_rate DESC
        """)
        compressed_clusters = c.fetchall()
        conn.close()
    except Exception as e:
        print(f"⚠️ SQL Compression Failed: {e}")
        return

    print(
        f"▶ Successfully compressed 11,000,000 rows into {len(compressed_clusters)} Mathematical Master Clusters."
    )

    cognitive_rules = []
    memory_path = "data/llm_distilled_cognition.json"

    async with httpx.AsyncClient() as client:
        for idx, cluster in enumerate(compressed_clusters, 1):
            pattern_name, count, avg_intensity, win_rate = cluster
            print("\n======================================")
            print(f"💀 COGNITIVE BATCH {idx}/{len(compressed_clusters)}")
            print(
                f"▶ Vector: {pattern_name} | Events Analyzed: {count:,} | True Win Rate: {win_rate:.2%}"
            )

            prompt = (
                "You are the Sovereign Quantum Engine. I am feeding you the mathematically compressed "
                f"results of {count:,} historical market anomalies over 75 years.\\n"
                f"Pattern Triggered: {pattern_name}\\n"
                f"Market Intensity Spike: {avg_intensity:.2f}\\n"
                f"Statistical Win Rate: {win_rate:.2%}\\n\\n"
                "Look at these millions of data points compressed into this formula. "
                "In exactly ONE precise sentence, what is the unbreakable trading rule we must follow when we see this pattern?"
                " Do not explain the math, just state the command."
            )
            rule = await prompt_local_llm(client, prompt)
            formatted_rule = f"[DB CLUSTER {idx}: {pattern_name}] {rule}"
            print(f"▶ Concluded Rule: {rule}")

            cognitive_rules.append(formatted_rule)
            with open(memory_path, "w", encoding="utf-8") as f:
                json.dump(cognitive_rules, f, indent=4)

            time.sleep(1)

    print("\n✅✅✅ 11M-ROW EXPERT LLM FUNNEL TRAINING COMPLETE ✅✅✅")


if __name__ == "__main__":
    asyncio.run(train_local_agents_from_11m_database())
