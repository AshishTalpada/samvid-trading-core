import json
import logging
import os

import torch
from datasets import Dataset, concatenate_datasets, load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

# Set CPU threads to keep system smooth
torch.set_num_threads(max(1, os.cpu_count() // 2))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SLM_Supercharger")

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
DATA_PATH = "data/slm_training_data.jsonl"
OUTPUT_DIR = "models/sovereign_slm_adapter"
MERGED_PATH = "models/sovereign_slm_merged"


def generate_synthetic_expert_data():
    """Generates 'Perfect Strategy' examples to reinforce core Sovereign logic."""
    logger.info("Generating Synthetic Strategy-Injection data...")
    synthetic = []

    rules = [
        # Dhatu: Vriddhi (Growth) -> BULLISH
        {
            "dhatu": "Vriddhi (Growth)",
            "regime": "Trending",
            "catalyst": 0.9,
            "side": "long",
            "target": "BULLISH",
        },
        # Dhatu: Kshaya (Decay) -> BEARISH
        {
            "dhatu": "Kshaya (Decay)",
            "regime": "Distribution",
            "catalyst": 0.2,
            "side": "short",
            "target": "BEARISH",
        },
        # Dhatu: Chala (Volatility) -> NEUTRAL
        {
            "dhatu": "Chala (Volatile)",
            "regime": "Sideways",
            "catalyst": 0.5,
            "side": "long",
            "target": "NEUTRAL",
        },
        # Contradiction: Bullish pattern but Fear Dhatu -> VETO (NEUTRAL)
        {
            "dhatu": "Viyoga (Fear)",
            "regime": "Bearish",
            "catalyst": 0.8,
            "side": "long",
            "target": "NEUTRAL",
        },
    ]

    system_prompt = "You are Sovereign-SLM, an elite quantitative strategist. Analyze the market context and output exactly one word: BULLISH, BEARISH, or NEUTRAL."

    for rule in rules:
        for _ in range(25):  # 100 total synthetic examples
            context = (
                f"Instrument: SYNTH_ASSET\n"
                f"Regime: {rule['regime']}\n"
                f"Dhatu State: {rule['dhatu']}\n"
                f"Pattern: Strategy_Reinforcement\n"
                f"Catalyst Score: {rule['catalyst']}\n"
                f"Belief: 0.9\n"
                f"\nDecision?"
            )
            synthetic.append(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Context:\n{context}"},
                        {"role": "assistant", "content": rule["target"]},
                    ]
                }
            )
    return Dataset.from_list(synthetic)


def train():
    if not os.path.exists(DATA_PATH):
        logger.error(f"Training data not found at {DATA_PATH}")
        return

    logger.info(" Starting SUPERCHARGED Sovereign SLM Training...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token

    # Load Base Model
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float32,
        device_map=None,
    )

    # SUPERCHARGED LoRA Config: High Rank (32) for deep strategy absorption
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=[
            "q_proj",
            "v_proj",
            "k_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.1,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load Real Data
    real_dataset = load_dataset("json", data_files=DATA_PATH, split="train")

    # Augment with Synthetic Strategy
    synth_dataset = generate_synthetic_expert_data()
    dataset = concatenate_datasets([real_dataset, synth_dataset]).shuffle(seed=42)

    def tokenize_function(examples):
        prompts = []
        for msg_list in examples["messages"]:
            system = msg_list[0]["content"]
            user = msg_list[1]["content"]
            assistant = msg_list[2]["content"]
            full_text = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n{assistant}<|im_end|>"
            prompts.append(full_text)

        tokenized = tokenizer(prompts, truncation=True, padding="max_length", max_length=128)
        tokenized["labels"] = [ids.copy() for ids in tokenized["input_ids"]]
        return tokenized

    tokenized_dataset = dataset.map(
        tokenize_function, batched=True, remove_columns=dataset.column_names
    )

    # Optimized Training Arguments for CPU Stability
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=4,
        learning_rate=1e-4,  # Slightly lower for deeper learning
        num_train_epochs=2,  # More epochs for the higher rank
        logging_steps=5,
        save_strategy="no",
        fp16=False,
        optim="adamw_torch",
        gradient_checkpointing=True,  # Saves RAM
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )

    logger.info(" Igniting the Sovereign Brain...")
    trainer.train()

    # Save and Merge
    model.save_pretrained(OUTPUT_DIR)
    logger.info(" Adapter saved. Merging weights...")

    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(MERGED_PATH)
    tokenizer.save_pretrained(MERGED_PATH)
    logger.info(f" MISSION COMPLETE: Supercharged brain ready at {MERGED_PATH}")


if __name__ == "__main__":
    train()
