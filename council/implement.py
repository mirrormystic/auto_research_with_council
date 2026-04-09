"""Spawn Claude Code CLI to implement the winning proposal."""

import subprocess
import sys
import logging
from pathlib import Path

from council.config import ChallengeConfig
from council.logger import log
from council import display


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

    # Mute stderr logger during Claude Code so its output isn't interleaved
    stderr_handler = None
    for h in log.handlers:
        if isinstance(h, logging.StreamHandler) and h.stream == sys.stderr:
            stderr_handler = h
            log.removeHandler(h)
            break

    print(f"\n{display.DIM}{'─' * 60}")
    print(f"  Claude Code working...{display.RESET}\n")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Edit,Write,Read,Bash"],
            cwd=challenge_dir,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"\n{display.DIM}{'─' * 60}{display.RESET}")
        if stderr_handler:
            log.addHandler(stderr_handler)
        log.error("Claude Code timed out after 300s")
        print(display.model_fail("Claude Code", "timed out after 300s"))
        return False

    print(f"\n{display.DIM}{'─' * 60}{display.RESET}")

    # Restore stderr logger
    if stderr_handler:
        log.addHandler(stderr_handler)

    if result.returncode != 0:
        log.error("Claude Code failed (rc=%d)", result.returncode)
        print(display.model_fail("Claude Code", f"exit code {result.returncode}"))
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
