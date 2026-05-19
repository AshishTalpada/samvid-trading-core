import json
import sys

from llama_cpp import Llama


def run_inference(model_path, prompt):
    try:
        # Load model FRESH for each isolated run to prevent state corruption
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=0,
            n_ctx=2048,
            n_threads=4,
            n_batch=8,  # Small batch for max stability
            verbose=False,
        )

        # Raw completion for speed
        full_prompt = f"System: {prompt[0]['content']}\nUser: {prompt[1]['content']}\nAssistant:"

        response = llm(full_prompt, max_tokens=20, temperature=0.1, stop=["\n", "User:", "System:"])

        result = response["choices"][0]["text"].strip().upper()
        print(json.dumps({"status": "SUCCESS", "text": result}))
    except Exception as e:
        print(json.dumps({"status": "ERROR", "reason": str(e)}))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    m_path = sys.argv[1]
    # Expect prompt as a JSON string from stdin to handle complex characters
    prompt_json = sys.stdin.read()
    p_list = json.loads(prompt_json)

    run_inference(m_path, p_list)
