import os

import requests

DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_BACKUP_MODEL_1 = "llama-3.3-70b-versatile"
DEFAULT_GROQ_BACKUP_MODEL_2 = "llama3-70b-8192"


def _call_groq_model(model, prompt, timeout, temperature, max_tokens, api_key):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    res = requests.post(DEFAULT_GROQ_URL, headers=headers, json=payload, timeout=timeout)
    if not res.ok:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:500]}")

    data = res.json()
    response = data["choices"][0]["message"]["content"].strip()
    if not response:
        raise ValueError(f"Groq returned an empty response for model {model}")

    return response


def call_groq(prompt, timeout=None, options=None):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    request_timeout = timeout or int(os.getenv("GROQ_TIMEOUT_SECONDS", "90"))
    temperature = 0.1
    max_tokens = None

    if options and "temperature" in options:
        temperature = options["temperature"]
    if options:
        max_tokens = options.get("max_tokens") or options.get("num_predict")

    primary = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    backup1 = os.getenv("GROQ_BACKUP_MODEL_1", DEFAULT_GROQ_BACKUP_MODEL_1)
    backup2 = os.getenv("GROQ_BACKUP_MODEL_2", DEFAULT_GROQ_BACKUP_MODEL_2)

    models = [primary, backup1, backup2]
    last_error = None

    for model in models:
        try:
            return _call_groq_model(model, prompt, request_timeout, temperature, max_tokens, api_key)
        except Exception as e:
            last_error = e
            print(f"[LLM] Model {model} failed: {e}. Trying next...")

    raise RuntimeError(f"All Groq models failed. Last error: {last_error}")


def call_llm(prompt, timeout=None, options=None):
    return call_groq(prompt, timeout=timeout, options=options)
