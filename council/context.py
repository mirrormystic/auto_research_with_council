"""Build prompts from challenge files and git history."""

from pathlib import Path

from council.config import ChallengeConfig
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

    return "\n".join(parts)


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

Respond with valid JSON only:
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

{proposals_text}

# YOUR TASK

Review every proposal above. For each one, provide:
- Strengths
- Weaknesses / risks
- Suggested modifications

You may also propose NEW ideas inspired by the discussion.

Respond with valid JSON only:
{{
  "critiques": [
    {{
      "proposal_id": 1,
      "strengths": "...",
      "weaknesses": "...",
      "suggestions": "..."
    }}
  ],
  "new_ideas": [
    {{
      "title": "...",
      "description": "...",
      "rationale": "...",
      "expected_impact": "small|medium|large"
    }}
  ]
}}"""


def build_vote_prompt(context: str, proposals_text: str, critiques_text: str) -> str:
    return f"""{context}

# PROPOSALS

{proposals_text}

# CRITIQUES

{critiques_text}

# YOUR TASK

Score every proposal from 1 (bad idea) to 5 (great idea, try this first).
Consider the critiques and experiment history.

Respond with valid JSON only:
{{
  "votes": [
    {{
      "proposal_id": 1,
      "score": 4,
      "reasoning": "brief reason"
    }}
  ]
}}"""
