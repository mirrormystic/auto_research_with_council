#!/usr/bin/env python3
"""Generate deep research prompts and import findings.

Generate a detailed research prompt from the current challenge state:
    python deep_research.py --challenge /tmp/council-test

Import research findings (paste from deep research tool):
    python deep_research.py --challenge /tmp/council-test --import

Findings are saved to research_findings.md in the challenge folder.
The council automatically picks them up on the next round.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from council.config import parse_program_md
from council.git import get_experiment_history, get_current_best, get_file_from_branch


RESEARCH_FINDINGS_FILE = "research_findings.md"


def generate_prompt(challenge_dir: Path) -> str:
    """Generate a detailed research prompt from current challenge state."""
    config = parse_program_md(challenge_dir / "program.md")
    history = get_experiment_history(challenge_dir)
    best_score, best_branch = get_current_best(challenge_dir, config.direction)

    # Get best strategy code
    best_code = ""
    if best_branch:
        code = get_file_from_branch(challenge_dir, best_branch, config.target_file)
        if code:
            best_code = code
    else:
        target_path = challenge_dir / config.target_file
        if target_path.exists():
            best_code = target_path.read_text()

    # Count experiments
    num_experiments = history.count("=== exp/")

    # Build the prompt
    parts = []

    parts.append("# Deep Research Request")
    parts.append("")
    parts.append("I'm working on an optimization problem and I've hit a plateau after multiple experiments.")
    parts.append("I need you to do deep research to find new approaches I haven't tried.")
    parts.append("")

    # Problem description
    parts.append("## The Problem")
    parts.append("")
    parts.append(config.program_md_raw)
    parts.append("")

    # Current state
    parts.append("## Current State")
    parts.append("")
    if best_score is not None:
        parts.append(f"- **Best score so far:** {best_score:.2f}")
        parts.append(f"- **Best branch:** {best_branch}")
    else:
        parts.append("- **Best score:** baseline (no improvements yet)")
    parts.append(f"- **Total experiments tried:** {num_experiments}")
    parts.append(f"- **Target file:** {config.target_file}")
    parts.append(f"- **Direction:** {config.direction}")
    parts.append("")

    # Best strategy code
    if best_code:
        parts.append("## Current Best Strategy Code")
        parts.append("")
        parts.append(f"```solidity")
        parts.append(best_code)
        parts.append("```")
        parts.append("")

    # Full experiment history
    parts.append("## Every Experiment Tried (with scores and detailed notes)")
    parts.append("")
    parts.append(history)
    parts.append("")

    # Reference files
    for ref in config.reference_files:
        ref_path = challenge_dir / ref
        if ref_path.exists():
            parts.append(f"## Reference File: {ref}")
            parts.append("")
            parts.append(f"```")
            parts.append(ref_path.read_text())
            parts.append("```")
            parts.append("")

    # Specific research questions
    parts.append("## What I Need You To Research")
    parts.append("")
    parts.append("Please investigate deeply. Search for papers, blog posts, forum discussions, code repositories, and competition write-ups.")
    parts.append("")
    parts.append("### Theoretical Questions")
    parts.append("- What does academic literature say about optimal fee strategies for constant-product AMMs?")
    parts.append("- What is the theoretical optimal spread for a market maker facing geometric Brownian motion price process?")
    parts.append("- What frameworks exist for balancing adverse selection (arbitrage losses) vs flow capture (retail volume)?")
    parts.append("- Are there closed-form solutions for the optimal dynamic fee given known volatility and flow parameters?")
    parts.append("")
    parts.append("### Practical Questions")
    parts.append("- What strategies have won similar competitions or challenges?")
    parts.append("- What approaches are used in Uniswap v4 hooks for dynamic fees?")
    parts.append("- Are there any open-source implementations of adaptive AMM fee strategies?")
    parts.append("- What do professional market makers do that could be adapted to this CFMM setting?")
    parts.append("")
    parts.append("### Analysis of My Experiments")
    parts.append("- Looking at my experiment history above, what patterns do you see in what worked vs what didn't?")
    parts.append("- What fundamental assumption might all my experiments be sharing that could be wrong?")
    parts.append("- What approaches are conspicuously MISSING from my experiment history?")
    parts.append("- Why is there still a large gap between my best score and the leaderboard? What am I missing?")
    parts.append("")
    parts.append("### Concrete Suggestions")
    parts.append("- Based on your research, propose 3-5 specific, concrete strategies I should try next")
    parts.append("- For each, explain the mathematical intuition and cite any relevant papers or implementations")
    parts.append("- Be specific about parameter values, formulas, and implementation details")
    parts.append("")

    return "\n".join(parts)


def import_findings(challenge_dir: Path) -> None:
    """Import research findings from stdin and append to findings file."""
    findings_path = challenge_dir / RESEARCH_FINDINGS_FILE

    print("Paste your deep research findings below.")
    print("Press Ctrl+D (or Ctrl+Z on Windows) when done:\n")

    try:
        content = sys.stdin.read().strip()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

    if not content:
        print("Error: no input provided")
        sys.exit(1)

    # Append with timestamp header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n\n---\n\n## Research Findings ({timestamp})\n\n{content}\n"

    with open(findings_path, "a") as f:
        f.write(entry)

    size = findings_path.stat().st_size
    print(f"\n✓ Findings appended to {findings_path}")
    print(f"  File size: {size:,} bytes")
    print(f"  The council will pick this up on the next round automatically.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate deep research prompts and import findings"
    )
    parser.add_argument("--challenge", required=True, help="Path to challenge folder")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="Import findings (paste from deep research tool)")
    args = parser.parse_args()

    challenge_dir = Path(args.challenge).resolve()
    program_path = challenge_dir / "program.md"
    if not program_path.exists():
        print(f"Error: {program_path} not found")
        sys.exit(1)

    if args.do_import:
        import_findings(challenge_dir)
    else:
        prompt = generate_prompt(challenge_dir)

        # Print to screen
        print(prompt)

        # Save to file
        prompt_path = challenge_dir / "research_prompt.md"
        prompt_path.write_text(prompt)
        print(f"\n{'─' * 60}")
        print(f"✓ Prompt saved to: {prompt_path}")
        print(f"  Paste this into ChatGPT Deep Research, Perplexity, or similar.")
        print(f"\n  When you get results back, run:")
        print(f"  python deep_research.py --challenge {challenge_dir} --import")


if __name__ == "__main__":
    main()
