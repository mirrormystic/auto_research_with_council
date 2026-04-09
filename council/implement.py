"""Spawn Claude Code CLI to implement the winning proposal."""

import subprocess
import sys
from pathlib import Path

from council.config import ChallengeConfig
from council.logger import log


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
    log.info("Implementation prompt:\n%s", prompt)

    # Stream output live to terminal (no capture) so user sees Claude working
    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "Edit,Write,Read,Bash"],
        cwd=challenge_dir,
        timeout=120,
    )

    if result.returncode != 0:
        log.error("Claude Code failed (rc=%d)", result.returncode)
        print(f"  ✗ Claude Code failed (exit code {result.returncode})")
        return False

    log.info("Claude Code finished successfully")

    # If there's a validate command, run it to double-check
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
            print(f"  ✗ Validation failed: {val_result.stdout[:200]}")
            return False

    log.info("Implementation succeeded, validation passed")
    print(f"  ✓ Compiled  ✓ Validated")
    return True
