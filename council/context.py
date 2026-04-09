"""Build prompts from challenge files and git history."""

from pathlib import Path

from council.logger import log
from council.config import ChallengeConfig
from council import display
from council.git import get_experiment_history, get_current_best, get_file_from_branch


def build_context(challenge_dir: Path, config: ChallengeConfig) -> str:
    """Build the full context string sent to models."""
    parts = []

    # 1. Program.md (full, including frontmatter)
    parts.append("# PROGRAM\n")
    parts.append(config.program_md_raw)

    # 2. Reference files
    for ref in config.reference_files:
        ref_path = challenge_dir / ref
        if ref_path.exists():
            parts.append(f"\n# REFERENCE FILE: {ref}\n```\n{ref_path.read_text()}```")

    # 3. Current target file (best version)
    best_score, best_branch = get_current_best(challenge_dir, config.direction)
    if best_branch:
        best_code = get_file_from_branch(challenge_dir, best_branch, config.target_file)
        if best_code:
            parts.append(
                f"\n# CURRENT BEST ({config.target_file}) — score: {best_score} "
                f"(branch: {best_branch})\n```\n{best_code}```"
            )
    else:
        target_path = challenge_dir / config.target_file
        if target_path.exists():
            parts.append(
                f"\n# CURRENT {config.target_file} (baseline)\n```\n{target_path.read_text()}```"
            )

    # 4. Experiment history
    history = get_experiment_history(challenge_dir)
    parts.append(f"\n# EXPERIMENT HISTORY\n{history}")

    # 5. Deep research findings (if any)
    findings_path = challenge_dir / "research_findings.md"
    has_research = False
    if findings_path.exists():
        findings = findings_path.read_text().strip()
        if findings:
            parts.append(f"\n# DEEP RESEARCH FINDINGS\n\nThe following research was conducted externally and may contain relevant theoretical insights, paper references, and concrete strategy suggestions.\n\n{findings}")
            has_research = True
            log.info("Loaded research findings: %d chars", len(findings))

    # Count experiments
    num_experiments = history.count("=== exp/")

    result = "\n".join(parts)
    log.info("Context built: %d chars, best_score=%s best_branch=%s, %d reference files",
             len(result), best_score, best_branch, len(config.reference_files))
    log.info("Experiment history:\n%s", history)

    # Show context info on screen
    print(display.context_info(
        context_len=len(result),
        best_score=best_score,
        best_branch=best_branch,
        num_experiments=num_experiments,
        num_ref_files=len(config.reference_files),
        target_file=config.target_file,
        has_research=has_research,
    ))

    return result


def build_propose_prompt(context: str, proposals_per_model: int) -> str:
    return f"""{context}

# YOUR TASK

You are one member of a research committee. Based on the problem description,
reference files, current best solution, and experiment history above, propose
{proposals_per_model} ideas for improving the score.

For each idea, explain:
- What to change and why
- Why you think it will improve the score
- Expected impact (small/medium/large)

You MUST respond with JSON matching this schema:
{{
  "ideas": [
    {{
      "title": "short title",
      "description": "detailed description of what to change",
      "rationale": "why this should work",
      "expected_impact": "small|medium|large"
    }}
  ]
}}"""


def build_critique_prompt(context: str, proposals_text: str) -> str:
    return f"""{context}

# PROPOSALS FROM THE COMMITTEE

All proposals are anonymous — you do not know who proposed what.

{proposals_text}

# YOUR TASK

Review every proposal above. For each one, provide:
- Strengths
- Weaknesses / risks
- Suggested modifications

Do NOT propose new ideas in this round — just critique.

You MUST respond with JSON matching this schema:
{{
  "critiques": [
    {{
      "proposal_id": 1,
      "strengths": "...",
      "weaknesses": "...",
      "suggestions": "..."
    }}
  ]
}}"""


def build_repropose_prompt(
    context: str,
    proposals_text: str,
    critiques_text: str,
    proposals_per_model: int,
) -> str:
    return f"""{context}

# EXISTING PROPOSALS (anonymous)

{proposals_text}

# CRITIQUES FROM THE COMMITTEE (anonymous)

{critiques_text}

# YOUR TASK

You have seen the initial proposals and the committee's critiques.
Now propose {proposals_per_model} NEW or REVISED ideas. You can:
- Propose entirely new ideas inspired by the discussion
- Improve on existing proposals based on the critiques
- Combine elements from multiple proposals

Do NOT repeat existing proposals unchanged.

You MUST respond with JSON matching this schema:
{{
  "ideas": [
    {{
      "title": "short title",
      "description": "detailed description of what to change",
      "rationale": "why this should work, addressing relevant critiques",
      "expected_impact": "small|medium|large"
    }}
  ]
}}"""


def build_vote_prompt(context: str, proposals_text: str, critiques_text: str) -> str:
    return f"""{context}

# ALL PROPOSALS (anonymous)

{proposals_text}

# ALL CRITIQUES (anonymous)

{critiques_text}

# YOUR TASK

Score every proposal from 0 (terrible, do not try) to 100 (excellent, try
this first). Consider the critiques, experiment history, and how likely
each idea is to improve the score.

Use the full range: 0 for clearly bad ideas, 30-50 for mediocre, 60-80
for promising, 90-100 for ideas you're confident will help.

You MUST respond with JSON matching this schema:
{{
  "votes": [
    {{
      "proposal_id": 1,
      "score": 75,
      "reasoning": "brief reason"
    }}
  ]
}}"""
