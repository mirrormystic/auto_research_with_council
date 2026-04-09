"""OpenRouter API client with tool calling and optional Tempo/MPP payment."""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from council.logger import log
from council.schemas import (
    PROPOSE_TOOL, CRITIQUE_TOOL, VOTE_TOOL,
    ProposeResponse, CritiqueResponse, VoteResponse,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MPP_URL = "https://openrouter.mpp.tempo.xyz/v1/chat/completions"
TEMPO_KEYS_PATH = Path.home() / ".tempo" / "wallet" / "keys.toml"
TEMPO_BIN = str(Path.home() / ".tempo" / "bin" / "tempo")

T = TypeVar("T", bound=BaseModel)


def _use_tempo() -> bool:
    return bool(os.environ.get("USE_TEMPO"))


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and not _use_tempo():
        raise RuntimeError(
            "Set OPENROUTER_API_KEY or use --tempo"
        )
    return key


async def _call_via_tempo(body: dict, timeout: float) -> dict:
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

    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()

    if proc.returncode != 0:
        # Log everything for debugging
        log.error("tempo request failed rc=%d model=%s", proc.returncode, body.get("model", "?"))
        log.error("tempo stderr: %s", stderr_str or "(empty)")
        log.error("tempo stdout: %s", stdout_str[:500] or "(empty)")
        raise RuntimeError(
            f"tempo request failed (rc={proc.returncode}) "
            f"model={body.get('model', '?')}: {stderr_str or stdout_str or 'no output'}"
        )

    return json.loads(stdout_str)


async def _call_via_api_key(body: dict, timeout: float) -> dict:
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


def _parse_tool_call(data: dict, response_model: type[T]) -> T | None:
    """Extract and validate a tool call response into a Pydantic model."""
    choices = data.get("choices", [])
    if not choices:
        log.warning("No choices in response")
        return None

    message = choices[0].get("message", {})

    # Try tool_calls first (standard function calling response)
    # Collect all candidate JSON strings to try
    candidates: list[str] = []

    # 1. Tool call arguments (primary)
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        args_str = tool_calls[0].get("function", {}).get("arguments", "")
        if args_str:
            candidates.append(args_str)

    # 2. Message content (fallback — some models ignore tool_choice)
    content = message.get("content", "")
    if content:
        candidates.append(content)
        # Also try extracting outermost { }
        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last > first:
            candidates.append(content[first:last + 1])

    # Try each candidate with multiple parsing strategies
    for candidate in candidates:
        # Strategy A: parse as JSON dict, then validate (handles double-serialized fields)
        try:
            raw = json.loads(candidate)
            if isinstance(raw, dict):
                # Recursively parse any string values that are themselves JSON
                raw = _deep_parse_json_strings(raw)
                return response_model.model_validate(raw)
        except (ValidationError, json.JSONDecodeError, TypeError):
            pass

        # Strategy B: direct JSON string validation
        try:
            return response_model.model_validate_json(candidate)
        except (ValidationError, json.JSONDecodeError):
            pass

    log.warning("Could not parse response into %s", response_model.__name__)
    log.debug("Raw response: %s", json.dumps(data, indent=2)[:2000])
    return None


def _deep_parse_json_strings(obj: dict) -> dict:
    """Recursively parse string values that look like JSON objects/arrays."""
    result = {}
    for key, value in obj.items():
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (dict, list)):
                    value = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(value, list):
            value = [_deep_parse_json_strings(v) if isinstance(v, dict) else v for v in value]
        elif isinstance(value, dict):
            value = _deep_parse_json_strings(value)
        result[key] = value
    return result


async def call_model_typed(
    model: str,
    prompt: str,
    tool: dict,
    response_model: type[T],
    *,
    timeout: float = 120.0,
) -> tuple[str, T | None, float]:
    """Call a model with tool calling. Returns (model_id, parsed_response, elapsed)."""
    use_tempo = _use_tempo()

    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4096,
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": tool["function"]["name"]}},
    }

    method = "tempo" if use_tempo else "api-key"
    log.debug("Calling model=%s tool=%s via=%s", model, tool["function"]["name"], method)
    start = time.monotonic()

    if use_tempo:
        data = await _call_via_tempo(body, timeout)
    else:
        data = await _call_via_api_key(body, timeout)

    elapsed = time.monotonic() - start
    parsed = _parse_tool_call(data, response_model)
    log.info("Model %s responded in %.1fs via %s, parsed=%s",
             model, elapsed, method, parsed is not None)
    log.debug("Model %s raw: %s", model, json.dumps(data, indent=2)[:3000])

    return model, parsed, elapsed


async def call_all_models_typed(
    models: list[str],
    prompt: str,
    tool: dict,
    response_model: type[T],
) -> list[tuple[str, T, float]]:
    """Call all models in parallel with tool calling. Returns only successful results."""
    tasks = [call_model_typed(m, prompt, tool, response_model) for m in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    good: list[tuple[str, T, float]] = []
    for r in results:
        if isinstance(r, Exception):
            log.error("Model call failed: %s", r)
            print(f"  ✗ Model failed: {r}")
        else:
            model, parsed, elapsed = r
            if parsed is not None:
                good.append((model, parsed, elapsed))
            else:
                short = model.split("/")[-1]
                log.warning("Model %s returned unparseable response", short)
                print(f"  ✗ {short}: response didn't match schema")
    log.info("call_all_models_typed: %d/%d succeeded", len(good), len(models))
    return good
