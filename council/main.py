"""CLI entry point and main loop."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from council.logger import log
from council.config import parse_program_md, load_council_config, ChallengeConfig, CouncilConfig
from council.context import build_context
from council.deliberate import run_deliberation, DeliberationResult
from council import display
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
    max_possible = len(result.vote_breakdown) * 100

    # Key critiques for this proposal (anonymous)
    critique_lines = []
    for c in winner.critiques[:3]:
        weakness = c.get("weaknesses", "")
        suggestion = c.get("suggestions", "")
        if weakness or suggestion:
            critique_lines.append(f"- {weakness} {suggestion}".strip())

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

        log.info("=== COUNCIL ROUND %d === Best: %s", round_num, best_display)
        print(display.header(round_num, best_display))

        # 1. Build context
        log.info("Building context from challenge dir")
        context = build_context(challenge_dir, challenge)
        log.info("Context built: %d chars", len(context))

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
            log.error("Deliberation failed: %s", e)
            print(display.model_fail("DELIBERATION", str(e)))
            print("  Retrying in next round...")
            continue

        # 5. Implement (try top 3)
        implemented = False
        for proposal in result.proposals[:3]:
            log.info("Attempting implementation: \"%s\" (by %s, score=%d)", proposal.title, proposal.source_model, proposal.score)
            print(display.implement_start(proposal.title))
            ok = implement_proposal(challenge_dir, challenge, proposal.description)
            if ok:
                # Update winner to the one that actually compiled
                result.winner = proposal
                implemented = True
                break
            print(f"  Trying next proposal...")

        if not implemented:
            log.warning("All top 3 proposals failed to implement, skipping round")
            print(display.model_fail("IMPLEMENT", "All top proposals failed. Skipping round."))
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

        if score is not None:
            log.info("Score: %.2f (best: %s) %s", score, best_display, "NEW BEST" if is_improvement else "")
            print(display.score_line(score, is_improvement))

        # Get diff for commit message
        import subprocess
        diff_result = subprocess.run(
            ["git", "diff", "HEAD", "--", challenge.target_file],
            cwd=challenge_dir,
            capture_output=True,
            text=True,
        )
        log.info("Implementation diff:\n%s", diff_result.stdout[:3000])
        diff = diff_result.stdout[:2000]

        branch_name = make_branch_name(score, result.winner.title)
        create_experiment_branch(challenge_dir, branch_name)
        msg = build_commit_message(result, score, challenge, diff)
        log.info("Commit message:\n%s", msg)
        commit_experiment(challenge_dir, [challenge.target_file], msg)

        # Print record
        proposer = result.winner.source_model.split("/")[-1]
        log.info("Recorded experiment: exp/%s (proposed by %s)", branch_name, proposer)
        print(display.record(branch_name, proposer))

        checkout_main(challenge_dir)
        log.info("Returned to main branch, starting next round")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Council — Multi-Model Autonomous Research")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the council loop")
    run_parser.add_argument("--challenge", type=str, default=".", help="Path to challenge folder")
    run_parser.add_argument("--models", type=str, required=True, help="Comma-separated model list (e.g. 'anthropic/claude-opus-4-6,openai/gpt-5.4,xai/grok-4.20')")
    run_parser.add_argument("--rounds", type=int, default=None, help="Deliberation rounds")
    payment = run_parser.add_mutually_exclusive_group(required=True)
    payment.add_argument("--tempo", action="store_true", help="Pay via Tempo MPP (requires `tempo wallet login`)")
    payment.add_argument("--openrouter-key", type=str, metavar="KEY", help="OpenRouter API key")

    args = parser.parse_args()
    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    # Set payment method
    if args.openrouter_key:
        os.environ["OPENROUTER_API_KEY"] = args.openrouter_key
        os.environ.pop("USE_TEMPO", None)
    elif args.tempo:
        os.environ["USE_TEMPO"] = "1"
        os.environ.pop("OPENROUTER_API_KEY", None)

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

    log.info("Council starting. challenge=%s target=%s models=%s rounds=%d direction=%s",
             challenge_dir, challenge.target_file, council.models, council.rounds, challenge.direction)
    print(f"Council — Multi-Model Autonomous Research")
    print(f"Challenge: {challenge_dir}")
    print(f"Target: {challenge.target_file}")
    print(f"Models: {', '.join(m.split('/')[-1] for m in council.models)}")
    print(f"Rounds: {council.rounds}")
    print(f"Direction: {challenge.direction}")
    print(f"Payment: {'Tempo MPP' if args.tempo else 'OpenRouter API key'}")
    print(f"Log file: council.log")

    asyncio.run(run_loop(challenge_dir, challenge, council))


if __name__ == "__main__":
    cli()
