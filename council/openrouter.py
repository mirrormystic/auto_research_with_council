"""OpenRouter API client with optional Tempo/MPP payment support."""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import httpx

from council.logger import log

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MPP_URL = "https://openrouter.mpp.tempo.xyz/v1/chat/completions"
TEMPO_KEYS_PATH = Path.home() / ".tempo" / "wallet" / "keys.toml"
TEMPO_BIN = str(Path.home() / ".tempo" / "bin" / "tempo")


def _use_tempo() -> bool:
    """Check if Tempo was explicitly requested via --tempo flag."""
    return bool(os.environ.get("USE_TEMPO"))


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and not _use_tempo():
        raise RuntimeError(
            "Set OPENROUTER_API_KEY for direct access, or "
            "run `tempo wallet login` for MPP payment"
        )
    return key


async def _call_via_tempo(body: dict, timeout: float) -> dict:
    """Call OpenRouter via `tempo request` CLI."""
    url = os.environ.get("OPENROUTER_MPP_URL", OPENROUTER_MPP_URL)
    body_json = json.dumps(body)

    log.info("Calling via tempo request: %s", url)
    proc = await asyncio.create_subprocess_exec(
        TEMPO_BIN, "request", "-X", "POST",
        "--json", body_json,
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(f"tempo request failed (rc={proc.returncode}): {err}")

    return json.loads(stdout.decode())


async def _call_via_api_key(body: dict, timeout: float) -> dict:
    """Call OpenRouter via API key."""
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/council",
        "X-Title": "Council - Multi-Model Research",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


async def call_model(
    model: str,
    prompt: str,
    *,
    thinking: str = "extended",
    timeout: float = 120.0,
) -> tuple[str, str, float]:
    """Call a model via OpenRouter. Returns (model_id, response_text, elapsed_seconds)."""
    use_tempo = _use_tempo()

    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    if thinking == "extended":
        if "anthropic" in model:
            body["transforms"] = ["middle-out"]

    method = "tempo" if use_tempo else "api-key"
    log.debug("Calling model=%s prompt_len=%d via=%s", model, len(prompt), method)
    start = time.monotonic()

    if use_tempo:
        data = await _call_via_tempo(body, timeout)
    else:
        data = await _call_via_api_key(body, timeout)

    elapsed = time.monotonic() - start
    text = data["choices"][0]["message"]["content"]
    log.info("Model %s responded in %.1fs, response_len=%d via %s", model, elapsed, len(text), method)
    log.debug("Model %s raw response:\n%s", model, text)
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
    try:
        result = json.loads(text)
        log.debug("extract_json: direct parse succeeded")
        return result
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    if "```" in text:
        start = text.index("```") + 3
        newline = text.index("\n", start)
        start = newline + 1
        end = text.index("```", start)
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    log.warning("extract_json: failed to parse JSON from response (len=%d): %s...", len(text), text[:200])
    return None
