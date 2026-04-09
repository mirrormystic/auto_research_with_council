#!/usr/bin/env python3
"""Create a challenge folder from a problem website + simulator GitHub repo.

Spawns Claude Code to read the website, clone the repo, understand the
simulator, and generate a properly structured challenge folder with
program.md, target file, and reference files.

Usage:
    python create_challenge.py \
        --url "https://www.optimizationarena.com/amm" \
        --repo "https://github.com/benedictbrady/amm-challenge" \
        --output ./challenges/amm

    python create_challenge.py \
        --url "https://some-competition.com/problem" \
        --repo "https://github.com/org/simulator" \
        --output ./challenges/my-problem
"""

import argparse
import subprocess
import sys
from pathlib import Path


PROMPT_TEMPLATE = """You are setting up a challenge folder for an autonomous research tool called "council".

Council runs a loop where multiple AI models brainstorm, critique, vote on, and test optimization ideas.
Each challenge is a git folder with a `program.md` and the files needed to run it.

YOUR TASK:

1. Go to this website and read the full problem description:
   {url}

2. Clone this GitHub repo and understand the simulator:
   {repo}

   - Figure out how to install and run it
   - Identify the evaluation command (how to score a solution)
   - Identify the metric (what number to extract from the output)
   - Identify the target file (what file gets modified to try different strategies)
   - Identify reference files (read-only files the target file depends on)

3. Create a challenge folder at: {output}

   The folder must contain:

   a. `program.md` — with YAML frontmatter + full problem description:
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
      <full problem description from the website>

      ## Scoring
      <how scoring works, what the metric means>

      ## What You Submit
      <what the target file looks like, API/interface to implement>

      ## Constraints
      <all constraints, limits, rules>

      ## Available Helpers
      <any utilities, base classes, helper functions available>

      ## Benchmarks
      <baseline scores, leaderboard scores if known>
      ```

   b. The target file (copy from the repo — the starting/baseline version)

   c. All reference files (copy from the repo — read-only dependencies)

   d. A `setup.sh` script that installs the simulator and its dependencies
      so that the eval command works when run from the challenge folder.
      Use `uv` for Python package management.

4. Initialize the folder as a git repo with an initial commit.

5. Test that the eval command actually works by running it.

IMPORTANT:
- Read the website thoroughly — don't guess the problem description
- Read the repo's README, source code, and tests to understand the simulator
- Make the program.md detailed enough that an AI model reading ONLY that file
  can understand the entire problem and propose solutions
- The eval command must work from inside the challenge folder
- Use relative paths in program.md
"""


def main():
    parser = argparse.ArgumentParser(
        description="Create a council challenge folder from a website + GitHub repo"
    )
    parser.add_argument("--url", required=True, help="Problem description website URL")
    parser.add_argument("--repo", required=True, help="Simulator GitHub repo URL")
    parser.add_argument("--output", required=True, help="Path for the new challenge folder")
    args = parser.parse_args()

    output = Path(args.output).resolve()

    if output.exists() and any(output.iterdir()):
        print(f"Error: {output} already exists and is not empty")
        sys.exit(1)

    output.mkdir(parents=True, exist_ok=True)

    prompt = PROMPT_TEMPLATE.format(
        url=args.url,
        repo=args.repo,
        output=output,
    )

    print(f"Creating challenge folder at: {output}")
    print(f"Problem URL: {args.url}")
    print(f"Simulator repo: {args.repo}")
    print(f"\n{'─' * 60}")
    print(f"  Spawning Claude Code...")
    print(f"{'─' * 60}\n")

    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--allowedTools", "Edit,Write,Read,Bash,WebFetch",
        ],
        cwd=str(output),
        timeout=600,
    )

    print(f"\n{'─' * 60}")

    if result.returncode != 0:
        print(f"Claude Code exited with code {result.returncode}")
        sys.exit(1)

    # Verify the folder was created properly
    program_md = output / "program.md"
    if program_md.exists():
        print(f"\n✓ Challenge folder created at: {output}")
        print(f"✓ program.md exists ({program_md.stat().st_size} bytes)")

        # Show the frontmatter
        content = program_md.read_text()
        if content.startswith("---"):
            end = content.index("---", 3)
            print(f"\nFrontmatter:\n{content[:end + 3]}")
    else:
        print(f"\n✗ program.md not found — challenge folder may be incomplete")
        sys.exit(1)

    print(f"\nTo run the council on this challenge:")
    print(f"  uv run council run --openrouter-key <KEY> --models \"anthropic/claude-sonnet-4-6,openai/gpt-4o\" --challenge {output}")


if __name__ == "__main__":
    main()
