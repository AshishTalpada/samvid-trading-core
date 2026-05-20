import json
import logging
import os
import sys

from llama_cpp import Llama

# Minimal logging to avoid terminal pollution
logging.basicConfig(level=logging.ERROR)


def run_isolated_inference(model_path, prompt_json):
    try:
        prompt = json.loads(prompt_json)
        n_ctx = int(os.environ.get("SOVEREIGN_SLM_N_CTX", "256"))
        n_threads = int(os.environ.get("SOVEREIGN_SLM_THREADS", "8"))
        n_gpu_layers = int(os.environ.get("SOVEREIGN_SLM_GPU_LAYERS", "0"))

        # Load fresh instance in isolation
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_batch=64,
            verbose=False,
        )

        # Use simple completion for max stability
        full_prompt = f"System: {prompt[0]['content']}\nUser: {prompt[1]['content']}\nAssistant:"

        response = llm(full_prompt, max_tokens=20, temperature=0.1, stop=["\n", "User:", "System:"])

        text = response["choices"][0]["text"].strip().upper()
        print(json.dumps({"status": "SUCCESS", "text": text}))
    except Exception as e:
        print(json.dumps({"status": "ERROR", "reason": str(e)}))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    m_path = sys.argv[1]
    p_json = sys.argv[2]

    run_isolated_inference(m_path, p_json)
