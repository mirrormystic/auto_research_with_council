"""CLI entry point and main loop."""

import argparse
import asyncio
import sys
from pathlib import Path

from council.config import parse_program_md, load_council_config, ChallengeConfig, CouncilConfig
from council.context import build_context
from council.deliberate import run_deliberation, DeliberationResult, format_critiques
from council.git import (
    get_current_best,
    create_experiment_branch,
    commit_experiment,
    checkout_main,
)
from council.implement import implement_proposal
from council.test import run_eval


def build_commit_message(
    result: DeliberationResult,
    score: float | None,
    config: ChallengeConfig,
    diff: str,
) -> str:
    """Build a detailed commit message from deliberation + score."""
    winner = result.winner
    score_str = f"{score:.2f}" if score is not None else "crash"

    # Vote breakdown
    vote_lines = []
    for model, votes in result.vote_breakdown.items():
        short = model.split("/")[-1]
        s = votes.get(winner.id, "?")
        vote_lines.append(f"{short}={s}")
    vote_str = ", ".join(vote_lines)
    total = winner.score
    max_possible = len(result.vote_breakdown) * 5

    # Key critiques for this proposal
    critique_lines = []
    for c in winner.critiques[:3]:
        reviewer = c.get("reviewer_model", "unknown").split("/")[-1]
        weakness = c.get("weaknesses", "")
        suggestion = c.get("suggestions", "")
        if weakness or suggestion:
            critique_lines.append(f"- {reviewer}: {weakness} {suggestion}".strip())

    msg_parts = [
        f"{winner.title} (score: {score_str})",
        "",
        f"Proposed by: {winner.source_model.split('/')[-1]}",
        f"Vote breakdown: {vote_str} (total: {total}/{max_possible})",
        "",
        f"Description:",
        winner.description,
        "",
        f"Rationale:",
        winner.rationale,
    ]

    if critique_lines:
        msg_parts.extend(["", "Key critiques:"] + critique_lines)

    if diff:
        msg_parts.extend(["", "Implementation:", diff])

    return "\n".join(msg_parts)


def make_branch_name(score: float | None, title: str) -> str:
    """Create a branch name from score + title."""
    slug = title.lower().replace(" ", "-")[:40]
    # Remove non-alphanumeric except hyphens
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-")
    if score is not None:
        return f"{score:.0f}-{slug}"
    return f"crash-{slug}"


async def run_loop(challenge_dir: Path, challenge: ChallengeConfig, council: CouncilConfig) -> None:
    """Main experiment loop. Runs forever."""
    round_num = 0

    while True:
        round_num += 1
        best_score, best_branch = get_current_best(challenge_dir, challenge.direction)
        best_display = f"{best_score:.2f}" if best_score else "none"

        print(f"\n{'=' * 55}")
        print(f"  COUNCIL ROUND {round_num}  |  Best: {best_display}")
        print(f"{'=' * 55}")

        # 1. Build context
        context = build_context(challenge_dir, challenge)

        # 2-4. Deliberation
        try:
            result = await run_deliberation(
                context,
                council.models,
                rounds=council.rounds,
                proposals_per_model=council.proposals_per_model,
                thinking=council.thinking,
            )
        except RuntimeError as e:
            print(f"\n  ✗ Deliberation failed: {e}")
            print("  Retrying in next round...")
            continue

        # 5. Implement (try top 3)
        implemented = False
        for proposal in result.proposals[:3]:
            print(f"\nIMPLEMENT  Claude Code working on: \"{proposal.title}\"")
            ok = implement_proposal(challenge_dir, challenge, proposal.description)
            if ok:
                # Update winner to the one that actually compiled
                result.winner = proposal
                implemented = True
                break
            print(f"  Trying next proposal...")

        if not implemented:
            print("  ✗ All top proposals failed to implement. Skipping round.")
            checkout_main(challenge_dir)
            continue

        # 6. Test
        score = run_eval(challenge_dir, challenge)

        # 7. Record
        is_improvement = False
        if score is not None and best_score is not None:
            if challenge.is_maximize:
                is_improvement = score > best_score
            else:
                is_improvement = score < best_score
        elif score is not None and best_score is None:
            is_improvement = True

        marker = " <- NEW BEST" if is_improvement else ""
        if score is not None:
            print(f"  Score: {score:.2f}{marker}")

        # Get diff for commit message
        import subprocess
        diff_result = subprocess.run(
            ["git", "diff", "HEAD", "--", challenge.target_file],
            cwd=challenge_dir,
            capture_output=True,
            text=True,
        )
        diff = diff_result.stdout[:2000]

        branch_name = make_branch_name(score, result.winner.title)
        create_experiment_branch(challenge_dir, branch_name)
        msg = build_commit_message(result, score, challenge, diff)
        commit_experiment(challenge_dir, [challenge.target_file], msg)

        # Print record
        proposer = result.winner.source_model.split("/")[-1]
        print(f"\nRECORD -> exp/{branch_name}")
        print(f"  Proposed by: {proposer}")

        checkout_main(challenge_dir)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Council — Multi-Model Autonomous Research")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the council loop")
    run_parser.add_argument("--challenge", type=str, default=".", help="Path to challenge folder")
    run_parser.add_argument("--models", type=str, default=None, help="Comma-separated model list")
    run_parser.add_argument("--rounds", type=int, default=None, help="Deliberation rounds")

    args = parser.parse_args()
    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    challenge_dir = Path(args.challenge).resolve()
    program_path = challenge_dir / "program.md"
    if not program_path.exists():
        print(f"Error: {program_path} not found")
        sys.exit(1)

    challenge = parse_program_md(program_path)
    overrides = {}
    if args.models:
        overrides["models"] = [m.strip() for m in args.models.split(",")]
    if args.rounds:
        overrides["rounds"] = args.rounds
    council = load_council_config(challenge_dir, overrides)

    print(f"Council — Multi-Model Autonomous Research")
    print(f"Challenge: {challenge_dir}")
    print(f"Target: {challenge.target_file}")
    print(f"Models: {', '.join(m.split('/')[-1] for m in council.models)}")
    print(f"Rounds: {council.rounds}")
    print(f"Direction: {challenge.direction}")

    asyncio.run(run_loop(challenge_dir, challenge, council))


if __name__ == "__main__":
    cli()
