#!/usr/bin/env python3
"""Create a challenge folder from a natural language description.

Spawns Claude Code to read any URLs mentioned, clone repos, understand
the simulator, and generate a properly structured challenge folder.

Usage:
    python create_challenge.py --output ./challenges/amm

    Then type your description, e.g.:
    "The problem is at https://www.optimizationarena.com/amm and the
     simulator is at https://github.com/benedictbrady/amm-challenge"
"""

import argparse
import subprocess
import sys
from pathlib import Path


SYSTEM_PROMPT = """You are setting up a challenge folder for an autonomous research tool called "council".

Council runs a loop where multiple AI models brainstorm, critique, vote on, and test optimization ideas.
Each challenge is a git folder with a `program.md` and the files needed to run it.

The user will describe the problem in plain text. They may give you URLs to websites and GitHub repos.

YOUR TASK:

1. Read any URLs the user mentioned — websites, GitHub repos, docs, etc.
   Use WebFetch and Bash (git clone) to get the full picture.

2. Figure out:
   - What the optimization problem is
   - How to install and run the simulator/evaluator
   - The evaluation command (how to score a solution)
   - The metric (what number to extract from the output, and the regex for it)
   - The target file (what file gets modified to try different strategies)
   - Reference files (read-only files the target file depends on)
   - Whether higher or lower score is better

3. Create the challenge folder with:

   a. `program.md` — YAML frontmatter + full problem description:
      ```
      ---
      target_file: <the file to optimize>
      reference_files:
        - <read-only dependency 1>
        - <read-only dependency 2>
      validate: "<command to check the solution compiles/is valid>"
      eval: "<command to score the solution>"
      metric_regex: "<regex to extract the score from eval output>"
      direction: <maximize or minimize>
      ---

      # Problem Title

      ## The Problem
      <full problem description>

      ## Scoring
      <how scoring works, what the metric means>

      ## What You Submit
      <what the target file looks like, API/interface to implement>

      ## Constraints
      <all constraints, limits, rules>

      ## Available Helpers
      <any utilities, base classes, helper functions>

      ## Benchmarks
      <baseline scores, leaderboard scores if known>
      ```

   b. The target file (copy the starting/baseline version)
   c. All reference files (read-only dependencies)
   d. A `setup.sh` script that installs the simulator so the eval command works

4. Initialize as a git repo with an initial commit.
5. Test that the eval command actually works by running it.

IMPORTANT:
- Read all URLs thoroughly — don't guess
- Make program.md detailed enough that an AI model reading ONLY that file
  can understand the entire problem and propose solutions
- The eval command must work from inside the challenge folder
- Use uv for Python package management
"""


def run_claude(prompt: str, cwd: str) -> int:
    """Run Claude Code in print mode. Output goes straight to terminal."""
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--allowedTools", "Edit,Write,Read,Bash,WebFetch",
            ],
            cwd=cwd,
            timeout=600,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print("Claude Code timed out after 600s")
        return -1


def main():
    parser = argparse.ArgumentParser(
        description="Create a council challenge folder from a plain text description"
    )
    parser.add_argument("--output", required=True, help="Path for the new challenge folder")
    args = parser.parse_args()

    output = Path(args.output).resolve()

    if output.exists() and any(output.iterdir()):
        print(f"Error: {output} already exists and is not empty")
        sys.exit(1)

    output.mkdir(parents=True, exist_ok=True)

    print("Describe the challenge in plain text.")
    print("Include any URLs (problem page, GitHub repo, docs).")
    print("Press Ctrl+D (or Ctrl+Z on Windows) when done:\n")

    try:
        user_input = sys.stdin.read().strip()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

    if not user_input:
        print("Error: no input provided")
        sys.exit(1)

    prompt = f"{SYSTEM_PROMPT}\n\nThe challenge folder should be created at: {output}\n\nUSER DESCRIPTION:\n{user_input}"

    print(f"\n{'─' * 60}")
    print(f"  Creating challenge at: {output}")
    print(f"{'─' * 60}\n")

    rc = run_claude(prompt, str(output))

    print(f"\n{'─' * 60}")

    if rc != 0:
        print(f"Claude Code exited with code {rc}")
        sys.exit(1)

    # Verify
    program_md = output / "program.md"
    if program_md.exists():
        print(f"\n✓ Challenge folder created at: {output}")
        print(f"✓ program.md exists ({program_md.stat().st_size} bytes)")

        content = program_md.read_text()
        if content.startswith("---"):
            try:
                end = content.index("---", 3)
                print(f"\nFrontmatter:\n{content[:end + 3]}")
            except ValueError:
                pass
    else:
        print(f"\n✗ program.md not found — challenge folder may be incomplete")
        sys.exit(1)

    print(f"\nTo run the council on this challenge:")
    print(f'  uv run council run --openrouter-key <KEY> --models "anthropic/claude-sonnet-4-6,openai/gpt-4o" --challenge {output}')


if __name__ == "__main__":
    main()
