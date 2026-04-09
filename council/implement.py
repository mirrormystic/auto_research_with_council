"""Spawn Claude Code CLI to implement the winning proposal."""

import subprocess
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
    log.debug("Implementation prompt:\n%s", prompt)

    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "Edit,Write,Read,Bash"],
        cwd=challenge_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )

    log.debug("Claude Code stdout:\n%s", result.stdout[:2000])
    if result.stderr:
        log.debug("Claude Code stderr:\n%s", result.stderr[:2000])

    if result.returncode != 0:
        log.error("Claude Code failed (rc=%d): %s", result.returncode, result.stderr[:500])
        print(f"  ✗ Claude Code failed: {result.stderr[:200]}")
        return False

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
        log.debug("Validation stdout: %s", val_result.stdout[:500])
        if val_result.returncode != 0:
            log.error("Validation failed: %s", val_result.stdout[:500])
            print(f"  ✗ Validation failed: {val_result.stdout[:200]}")
            return False

    log.info("Implementation succeeded, validation passed")
    print(f"  ✓ Compiled  ✓ Validated")
    return True
