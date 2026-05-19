import json
import logging
import sys

from llama_cpp import Llama

# Minimal logging to avoid terminal pollution
logging.basicConfig(level=logging.ERROR)


def run_isolated_inference(model_path, prompt_json):
    try:
        prompt = json.loads(prompt_json)

        # Load fresh instance in isolation
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=2048,
            n_threads=16,
            n_batch=1,
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
