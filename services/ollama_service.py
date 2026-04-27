import os

import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODELS = ("phi3", "mistral:7b", "llama3:8b")
MIN_TIMEOUT_SECONDS = 120
DEFAULT_NUM_CTX = 1024
DEFAULT_NUM_PREDICT = 512


def configured_models():
    configured = os.getenv("LOCAL_LLM_MODELS") or os.getenv("OLLAMA_MODEL")
    if not configured:
        return list(DEFAULT_OLLAMA_MODELS)

    models = [model.strip() for model in configured.split(",") if model.strip()]
    return models or list(DEFAULT_OLLAMA_MODELS)


def call_local_llm(prompt, timeout=None, options=None):
    url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    configured_timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    request_timeout = max(MIN_TIMEOUT_SECONDS, configured_timeout)
    default_options = {
        "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", str(DEFAULT_NUM_CTX))),
        "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", str(DEFAULT_NUM_PREDICT))),
    }
    if options:
        default_options.update(options)
    errors = []

    for model_name in configured_models():
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }

        payload["options"] = default_options

        try:
            res = requests.post(url, json=payload, timeout=request_timeout)
            if not res.ok:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:500]}")

            data = res.json()
            response = data.get("response", "").strip()
            if not response:
                raise ValueError("Ollama returned an empty response")

            return response
        except Exception as e:
            errors.append(f"{model_name}: {e}")

    raise RuntimeError("All configured Ollama models failed. " + " | ".join(errors))


def call_phi3(prompt, timeout=None, options=None):
    return call_local_llm(prompt, timeout=timeout, options=options)
