"""Deliberation pipeline: propose → critique → vote."""

import asyncio
import random
from dataclasses import dataclass, field

from council.openrouter import call_all_models, extract_json
from council.context import build_propose_prompt, build_critique_prompt, build_vote_prompt


@dataclass
class Proposal:
    id: int
    title: str
    description: str
    rationale: str
    expected_impact: str
    source_model: str  # which model proposed it
    score: int = 0
    critiques: list[dict] = field(default_factory=list)


@dataclass
class DeliberationResult:
    proposals: list[Proposal]
    winner: Proposal
    vote_breakdown: dict[str, dict[int, int]]  # model -> {proposal_id: score}
    all_critiques: list[dict]


async def run_deliberation(
    context: str,
    models: list[str],
    *,
    rounds: int = 3,
    proposals_per_model: int = 3,
    thinking: str = "extended",
) -> DeliberationResult:
    """Run the full deliberation pipeline."""

    # --- ROUND 1: PROPOSE ---
    print(f"\nPROPOSE  {len(models)} models x {proposals_per_model} ideas")
    propose_prompt = build_propose_prompt(context, proposals_per_model)
    responses = await call_all_models(models, propose_prompt, thinking=thinking)

    proposals: list[Proposal] = []
    proposal_id = 1
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data and "ideas" in data:
            count = 0
            for idea in data["ideas"]:
                proposals.append(Proposal(
                    id=proposal_id,
                    title=idea.get("title", f"Idea {proposal_id}"),
                    description=idea.get("description", ""),
                    rationale=idea.get("rationale", ""),
                    expected_impact=idea.get("expected_impact", "medium"),
                    source_model=model,
                ))
                proposal_id += 1
                count += 1
            print(f"  ✓ {short:20s} {count} ideas ({elapsed:.1f}s)")
        else:
            print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")

    if not proposals:
        raise RuntimeError("No proposals received from any model")

    # Format proposals for critique/vote rounds (anonymous)
    proposals_text = format_proposals(proposals, anonymous=True)

    all_critiques: list[dict] = []

    # --- ROUNDS 2+: CRITIQUE ---
    for round_num in range(2, rounds + 1):
        if round_num < rounds:
            # Critique round
            print(f"\nCRITIQUE  {len(models)} models reviewing {len(proposals)} proposals")
            critique_prompt = build_critique_prompt(context, proposals_text)
            responses = await call_all_models(models, critique_prompt, thinking=thinking)

            critiques_parts = []
            for model, text, elapsed in responses:
                short = model.split("/")[-1]
                data = extract_json(text)
                if data:
                    # Attach critiques to proposals
                    for c in data.get("critiques", []):
                        pid = c.get("proposal_id")
                        c["reviewer_model"] = model
                        all_critiques.append(c)
                        for p in proposals:
                            if p.id == pid:
                                p.critiques.append(c)
                    # Add new ideas
                    for idea in data.get("new_ideas", []):
                        proposals.append(Proposal(
                            id=proposal_id,
                            title=idea.get("title", f"New idea {proposal_id}"),
                            description=idea.get("description", ""),
                            rationale=idea.get("rationale", ""),
                            expected_impact=idea.get("expected_impact", "medium"),
                            source_model=model,
                        ))
                        proposal_id += 1
                    critiques_parts.append(f"Reviewer:\n{text}")
                    print(f"  ✓ {short:20s} ({elapsed:.1f}s)")
                else:
                    print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")

            critiques_text = "\n\n".join(critiques_parts)
            # Update proposals text with new ideas
            proposals_text = format_proposals(proposals, anonymous=True)
        else:
            # Final round: VOTE
            print(f"\nVOTE  {len(models)} models scoring {len(proposals)} proposals")
            critiques_text = format_critiques(all_critiques)
            vote_prompt = build_vote_prompt(context, proposals_text, critiques_text)
            responses = await call_all_models(models, vote_prompt, thinking=thinking)

            vote_breakdown: dict[str, dict[int, int]] = {}
            for model, text, elapsed in responses:
                short = model.split("/")[-1]
                data = extract_json(text)
                if data and "votes" in data:
                    model_votes = {}
                    for v in data["votes"]:
                        pid = v.get("proposal_id")
                        score = min(5, max(1, int(v.get("score", 3))))
                        model_votes[pid] = score
                        for p in proposals:
                            if p.id == pid:
                                p.score += score
                    vote_breakdown[model] = model_votes
                    print(f"  ✓ {short:20s} ({elapsed:.1f}s)")
                else:
                    print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")

    # Sort by score, break ties randomly
    random.shuffle(proposals)  # randomize before sort for tie-breaking
    proposals.sort(key=lambda p: p.score, reverse=True)

    # Print top 3
    print()
    for i, p in enumerate(proposals[:3]):
        print(f"  #{i+1}  \"{p.title}\"  Score: {p.score}")

    return DeliberationResult(
        proposals=proposals,
        winner=proposals[0],
        vote_breakdown=vote_breakdown if 'vote_breakdown' in dir() else {},
        all_critiques=all_critiques,
    )


def format_proposals(proposals: list[Proposal], *, anonymous: bool) -> str:
    parts = []
    for p in proposals:
        source = "" if anonymous else f" (by {p.source_model.split('/')[-1]})"
        parts.append(
            f"## Proposal {p.id}: {p.title}{source}\n"
            f"Description: {p.description}\n"
            f"Rationale: {p.rationale}\n"
            f"Expected impact: {p.expected_impact}"
        )
    return "\n\n".join(parts)


def format_critiques(critiques: list[dict]) -> str:
    parts = []
    for c in critiques:
        pid = c.get("proposal_id", "?")
        parts.append(
            f"On proposal {pid}:\n"
            f"  Strengths: {c.get('strengths', 'N/A')}\n"
            f"  Weaknesses: {c.get('weaknesses', 'N/A')}\n"
            f"  Suggestions: {c.get('suggestions', 'N/A')}"
        )
    return "\n".join(parts)
