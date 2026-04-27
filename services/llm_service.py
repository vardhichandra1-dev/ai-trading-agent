import os

import requests

from services.ollama_service import call_local_llm


DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def call_groq(prompt, timeout=None, options=None):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    request_timeout = timeout or int(os.getenv("GROQ_TIMEOUT_SECONDS", "90"))
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    temperature = 0.1

    if options and "temperature" in options:
        temperature = options["temperature"]

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    res = requests.post(DEFAULT_GROQ_URL, headers=headers, json=payload, timeout=request_timeout)
    if not res.ok:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:500]}")

    data = res.json()
    response = data["choices"][0]["message"]["content"].strip()
    if not response:
        raise ValueError(f"Groq returned an empty response for model {model}")

    return response


def call_llm(prompt, timeout=None, options=None):
    try:
        return call_groq(prompt, timeout=timeout, options=options)
    except Exception as groq_error:
        try:
            return call_local_llm(prompt, timeout=timeout, options=options)
        except Exception as local_error:
            raise RuntimeError(
                "Groq primary and local Ollama fallback both failed. "
                f"Groq: {groq_error} | Local: {local_error}"
            ) from local_error
