from __future__ import annotations

import time
from typing import Any

import ollama
import requests

import config


def _chat_ollama(system_prompt: str, user_prompt: str, temperature: float) -> str:
    kwargs = {"host": config.OLLAMA_HOST} if config.OLLAMA_HOST else {}
    client = ollama.Client(**kwargs) if kwargs else ollama
    resp = client.chat(
        model=config.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": temperature},
    )
    return str(resp.get("message", {}).get("content", "")).strip()


def _chat_openai(system_prompt: str, user_prompt: str, temperature: float) -> str:
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing.")

    base = config.OPENAI_BASE_URL.rstrip("/")
    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": config.OPENAI_MODEL or config.DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(config.OPENAI_MAX_RETRIES + 1):
        resp = requests.post(
            url,
            json=payload,
            timeout=max(30, config.REQUEST_TIMEOUT_SEC * 3),
            headers=headers,
        )
        if resp.status_code != 429:
            resp.raise_for_status()
            body = resp.json()
            return str(body.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()

        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                wait_sec = float(retry_after)
            except ValueError:
                wait_sec = config.OPENAI_RETRY_BASE_SEC * (2**attempt)
        else:
            wait_sec = config.OPENAI_RETRY_BASE_SEC * (2**attempt)
        last_error = requests.HTTPError(f"429 Too Many Requests (attempt {attempt + 1})")
        if attempt >= config.OPENAI_MAX_RETRIES:
            break
        time.sleep(min(wait_sec, 90.0))

    raise RuntimeError(
        f"OpenAI rate limit persisted after {config.OPENAI_MAX_RETRIES + 1} attempts. "
        "Reduce request volume or increase tier."
    ) from last_error


def chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    provider = config.AI_PROVIDER
    if provider == "openai":
        return _chat_openai(system_prompt, user_prompt, temperature)
    if provider == "ollama":
        return _chat_ollama(system_prompt, user_prompt, temperature)
    raise ValueError(f"Unsupported AI_PROVIDER: {provider}. Use 'ollama' or 'openai'.")
