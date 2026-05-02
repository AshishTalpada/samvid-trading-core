import logging
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SLM_Merger")

BASE_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = "models/sovereign_slm_adapter"
MERGED_PATH = "models/sovereign_slm_merged"


def merge():
    if not os.path.exists(ADAPTER_PATH):
        logger.error(f"Adapter not found at {ADAPTER_PATH}")
        return

    logger.info("Starting Brain Consolidation (Merging LoRA weights)...")

    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.float32,
        device_map=None,
    )

    # Load adapter
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)

    # Merge and unload
    logger.info("Applying learned weights to base DNA...")
    merged_model = model.merge_and_unload()

    # Save
    logger.info(f"Saving merged Sovereign brain to {MERGED_PATH}...")
    merged_model.save_pretrained(MERGED_PATH)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    tokenizer.save_pretrained(MERGED_PATH)

    logger.info("✅ Consolidation complete. The SLM is now a unified expert.")


if __name__ == "__main__":
    merge()
