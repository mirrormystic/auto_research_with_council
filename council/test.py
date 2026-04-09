"""Run evaluation and extract score."""

import re
import subprocess
from pathlib import Path

from council.config import ChallengeConfig
from council.logger import log


def run_eval(challenge_dir: Path, config: ChallengeConfig) -> float | None:
    """Run the eval command and extract the score."""
    log.info("Running eval: %s", config.eval)
    print(f"\nTEST")
    print(f"  Running: {config.eval}")

    result = subprocess.run(
        config.eval,
        shell=True,
        cwd=challenge_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )

    output = result.stdout + result.stderr
    log.debug("Eval output:\n%s", output[:2000])

    match = re.search(config.metric_regex, output)
    if match:
        score = float(match.group(1))
        log.info("Score extracted: %.2f", score)
        print(f"  Score: {score}")
        return score

    log.error("Could not extract score. regex=%s stdout=%s stderr=%s",
              config.metric_regex, result.stdout[:300], result.stderr[:300])
    print(f"  ✗ Could not extract score from output")
    print(f"    stdout: {result.stdout[:300]}")
    print(f"    stderr: {result.stderr[:300]}")
    return None
