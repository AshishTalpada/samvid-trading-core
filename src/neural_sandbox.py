import json
import logging
import os
import sys
from typing import Any

from llama_cpp import Llama

logging.basicConfig(level=logging.ERROR)


def _safe_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _load_model(model_path: str) -> tuple[Llama, dict[str, int]]:
    n_ctx = _safe_int_env("SOVEREIGN_SLM_N_CTX", 256, 128, 1024)
    n_threads = _safe_int_env("SOVEREIGN_SLM_THREADS", 4, 1, 4)
    n_gpu_layers = _safe_int_env("SOVEREIGN_SLM_GPU_LAYERS", 0, 0, 99)
    n_batch = _safe_int_env("SOVEREIGN_SLM_N_BATCH", 4, 1, 16)
    n_ubatch = _safe_int_env("SOVEREIGN_SLM_N_UBATCH", min(n_batch, 4), 1, n_batch)

    kwargs: dict[str, Any] = {
        "model_path": model_path,
        "n_gpu_layers": n_gpu_layers,
        "n_ctx": n_ctx,
        "n_threads": n_threads,
        "n_batch": n_batch,
        "verbose": False,
    }
    try:
        llm = Llama(**kwargs, n_ubatch=n_ubatch, flash_attn=False)
    except TypeError:
        llm = Llama(**kwargs)

    return llm, {
        "n_ctx": n_ctx,
        "n_threads": n_threads,
        "n_gpu_layers": n_gpu_layers,
        "n_batch": n_batch,
        "n_ubatch": n_ubatch,
    }


def _complete(llm: Llama, prompt: list[dict[str, str]], max_tokens: int, temperature: float) -> str:
    full_prompt = f"System: {prompt[0]['content']}\nUser: {prompt[1]['content']}\nAssistant:"
    response = llm(
        full_prompt,
        max_tokens=max(1, min(int(max_tokens), 20)),
        temperature=float(temperature),
        stop=["\n", "User:", "System:"],
    )
    return str(response["choices"][0]["text"]).strip().upper()


def run_isolated_inference(model_path: str, prompt_json: str) -> None:
    try:
        prompt = json.loads(prompt_json)
        llm, _meta = _load_model(model_path)
        text = _complete(llm, prompt, max_tokens=3, temperature=0.1)
        print(json.dumps({"status": "SUCCESS", "text": text}), flush=True)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}), flush=True)


def run_worker(model_path: str) -> None:
    try:
        llm, meta = _load_model(model_path)
        print(json.dumps({"status": "READY", **meta}), flush=True)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}), flush=True)
        return

    for line in sys.stdin:
        try:
            request = json.loads(line)
            text = _complete(
                llm,
                request["prompt"],
                max_tokens=int(request.get("max_tokens", 10)),
                temperature=float(request.get("temperature", 0.1)),
            )
            print(
                json.dumps(
                    {"id": request.get("id"), "status": "SUCCESS", "text": text},
                    separators=(",", ":"),
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                json.dumps(
                    {"id": request.get("id") if "request" in locals() else None,
                     "status": "ERROR",
                     "reason": str(exc)},
                    separators=(",", ":"),
                ),
                flush=True,
            )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        run_worker(sys.argv[2])
    elif len(sys.argv) >= 3:
        run_isolated_inference(sys.argv[1], sys.argv[2])
    else:
        sys.exit(1)
