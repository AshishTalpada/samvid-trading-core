import logging
import os

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SLM_Trainer")

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
DATA_PATH = "data/slm_training_data.jsonl"
OUTPUT_DIR = "models/sovereign_slm_adapter"


def train():
    if not os.path.exists(DATA_PATH):
        logger.error(f"Training data not found at {DATA_PATH}")
        return

    logger.info("Initializing Sovereign SLM Training Sequence...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float32,
        device_map=None if device == "cpu" else "auto",
    )

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

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

    dataset = load_dataset("json", data_files=DATA_PATH, split="train")
    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["messages"])

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=4,
        learning_rate=2e-4,
        num_train_epochs=2,
        logging_steps=5,
        save_strategy="no",
        fp16=False,
        optim="adamw_torch",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )

    logger.info("🚀 Training started (Optimized for CPU speed)...")
    trainer.train()

    # Save the adapter
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info(f"✅ Adapter saved to {OUTPUT_DIR}")

    # Merge and save as full model for easier GGUF conversion later
    logger.info("Merging LoRA weights into base model...")
    merged_model = model.merge_and_unload()
    merged_path = "models/sovereign_slm_merged"
    merged_model.save_pretrained(merged_path)
    tokenizer.save_pretrained(merged_path)
    logger.info(f"✅ Merged model saved to {merged_path}")


if __name__ == "__main__":
    train()
