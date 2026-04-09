"""OpenRouter API client."""

import asyncio
import json
import os
import time

import httpx

from council.logger import log

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    return key


async def call_model(
    model: str,
    prompt: str,
    *,
    thinking: str = "extended",
    timeout: float = 120.0,
) -> tuple[str, str, float]:
    """Call a model via OpenRouter. Returns (model_id, response_text, elapsed_seconds)."""
    api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/council",
        "X-Title": "Council - Multi-Model Research",
    }

    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    # Request extended thinking for models that support it
    if thinking == "extended":
        if "anthropic" in model:
            body["transforms"] = ["middle-out"]
        # Other providers handle thinking via model selection

    log.debug("Calling model=%s prompt_len=%d", model, len(prompt))
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    elapsed = time.monotonic() - start
    text = data["choices"][0]["message"]["content"]
    log.info("Model %s responded in %.1fs, response_len=%d", model, elapsed, len(text))
    log.debug("Model %s full response:\n%s", model, text)
    return model, text, elapsed


async def call_all_models(
    models: list[str],
    prompt: str,
    *,
    thinking: str = "extended",
) -> list[tuple[str, str, float]]:
    """Call all models in parallel. Returns list of (model, response, elapsed)."""
    tasks = [call_model(m, prompt, thinking=thinking) for m in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    good = []
    for r in results:
        if isinstance(r, Exception):
            log.error("Model call failed: %s", r)
            print(f"  ✗ Model failed: {r}")
        else:
            good.append(r)
    log.info("call_all_models: %d/%d succeeded", len(good), len(models))
    return good


def extract_json(text: str) -> dict | None:
    """Extract JSON from a model response that might have markdown fences."""
    # Try direct parse first
    try:
        result = json.loads(text)
        log.debug("extract_json: direct parse succeeded")
        return result
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Try extracting from ``` ... ``` blocks
    if "```" in text:
        start = text.index("```") + 3
        # Skip optional language identifier on same line
        newline = text.index("\n", start)
        start = newline + 1
        end = text.index("```", start)
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    log.warning("extract_json: failed to parse JSON from response (len=%d): %s...", len(text), text[:200])
    return None
