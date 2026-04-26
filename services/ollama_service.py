import os

import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_REASONING_MODEL = "llama3:8b-instruct"
DEFAULT_QUERY_MODEL = "mistral:7b-instruct"


def call_ollama(prompt, model=None, timeout=None, options=None):
    url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model_name = model or os.getenv("OLLAMA_REASONING_MODEL", DEFAULT_REASONING_MODEL)
    request_timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }

    if options:
        payload["options"] = options

    res = requests.post(url, json=payload, timeout=request_timeout)
    res.raise_for_status()

    data = res.json()
    response = data.get("response", "").strip()
    if not response:
        raise ValueError(f"Ollama returned an empty response for model {model_name}")

    return response


def call_query_model(prompt):
    return call_ollama(
        prompt,
        model=os.getenv("OLLAMA_QUERY_MODEL", DEFAULT_QUERY_MODEL),
        timeout=int(os.getenv("OLLAMA_QUERY_TIMEOUT_SECONDS", "90")),
        options={"temperature": 0.2},
    )


def call_reasoning_model(prompt):
    return call_ollama(
        prompt,
        model=os.getenv("OLLAMA_REASONING_MODEL", DEFAULT_REASONING_MODEL),
        timeout=int(os.getenv("OLLAMA_REASONING_TIMEOUT_SECONDS", "240")),
        options={"temperature": 0.1},
    )
