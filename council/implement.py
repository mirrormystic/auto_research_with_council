"""Spawn Claude Code CLI to implement the winning proposal."""

import json
import subprocess
import sys
import logging
from pathlib import Path

from council.config import ChallengeConfig
from council.logger import log
from council import display


def _stream_claude(prompt: str, cwd: Path, timeout: int = 300) -> int:
    """Run Claude Code with streaming output. Returns exit code."""
    proc = subprocess.Popen(
        [
            "claude", "-p", prompt,
            "--allowedTools", "Edit,Write,Read,Bash",
            "--output-format", "stream-json",
        ],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
    )

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "assistant":
                msg = event.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                print(f"  {display.DIM}{block['text']}{display.RESET}")
                            elif block.get("type") == "tool_use":
                                tool = block.get("name", "")
                                inp = block.get("input", {})
                                if tool == "Bash":
                                    print(f"  {display.CYAN}$ {inp.get('command', '')}{display.RESET}")
                                elif tool == "Write":
                                    print(f"  {display.YELLOW}Writing: {inp.get('file_path', '').split('/')[-1]}{display.RESET}")
                                elif tool == "Edit":
                                    print(f"  {display.YELLOW}Editing: {inp.get('file_path', '').split('/')[-1]}{display.RESET}")
                                elif tool == "Read":
                                    print(f"  {display.BLUE}Reading: {inp.get('file_path', '').split('/')[-1]}{display.RESET}")
                                else:
                                    print(f"  {display.DIM}[{tool}]{display.RESET}")
                elif isinstance(content, str) and content:
                    print(f"  {display.DIM}{content}{display.RESET}")

            elif etype == "result":
                result_text = event.get("result", "")
                if result_text:
                    print(f"  {display.GREEN}{result_text[:200]}{display.RESET}")

        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1

    return proc.returncode


def implement_proposal(
    challenge_dir: Path,
    config: ChallengeConfig,
    proposal_description: str,
) -> bool:
    """Use Claude Code CLI to implement a proposal. Returns True if validation passes."""
    prompt = (
        f"Read the file {config.target_file}. "
        f"Implement this change:\n\n{proposal_description}\n\n"
        f"Write the modified file. "
    )
    if config.validate:
        prompt += f"Then validate by running: {config.validate}"

    log.info("Spawning Claude Code CLI to implement proposal")
    log.debug("Implementation prompt:\n%s", prompt)

    # Mute stderr logger during Claude Code
    stderr_handler = None
    for h in log.handlers:
        if isinstance(h, logging.StreamHandler) and h.stream == sys.stderr:
            stderr_handler = h
            log.removeHandler(h)
            break

    print(f"\n{display.DIM}{'─' * 60}")
    print(f"  Claude Code implementing...{display.RESET}\n")

    rc = _stream_claude(prompt, challenge_dir)

    print(f"\n{display.DIM}{'─' * 60}{display.RESET}")

    # Restore stderr logger
    if stderr_handler:
        log.addHandler(stderr_handler)

    if rc == -1:
        log.error("Claude Code timed out after 300s")
        print(display.model_fail("Claude Code", "timed out after 300s"))
        return False

    if rc != 0:
        log.error("Claude Code failed (rc=%d)", rc)
        print(display.model_fail("Claude Code", f"exit code {rc}"))
        return False

    log.info("Claude Code finished successfully")

    # Validate
    if config.validate:
        log.info("Running validation: %s", config.validate)
        val_result = subprocess.run(
            config.validate,
            shell=True,
            cwd=challenge_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        log.info("Validation output: %s", val_result.stdout.strip())
        if val_result.returncode != 0:
            log.error("Validation failed: %s", val_result.stdout[:500])
            print(display.model_fail("Validation", val_result.stdout[:200]))
            return False

    log.info("Implementation succeeded, validation passed")
    print(f"  {display.GREEN}✓ Compiled  ✓ Validated{display.RESET}")
    return True
