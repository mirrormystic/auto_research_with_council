"""Run evaluation and extract score."""

import re
import subprocess
from pathlib import Path

from council.config import ChallengeConfig


def run_eval(challenge_dir: Path, config: ChallengeConfig) -> float | None:
    """Run the eval command and extract the score."""
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
    match = re.search(config.metric_regex, output)
    if match:
        score = float(match.group(1))
        print(f"  Score: {score}")
        return score

    print(f"  ✗ Could not extract score from output")
    print(f"    stdout: {result.stdout[:300]}")
    print(f"    stderr: {result.stderr[:300]}")
    return None
