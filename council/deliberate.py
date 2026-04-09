"""Deliberation pipeline: propose → critique → propose → critique → vote."""

import random
from dataclasses import dataclass, field

from council.logger import log
from council.openrouter import call_all_models_typed
from council.schemas import (
    PROPOSE_TOOL, CRITIQUE_TOOL, VOTE_TOOL,
    ProposeResponse, CritiqueResponse, VoteResponse,
)
from council.context import build_propose_prompt, build_critique_prompt, build_repropose_prompt, build_vote_prompt
from council import display


@dataclass
class Proposal:
    id: int
    title: str
    description: str
    rationale: str
    expected_impact: str
    source_model: str
    score: int = 0
    critiques: list[dict] = field(default_factory=list)


@dataclass
class DeliberationResult:
    proposals: list[Proposal]
    winner: Proposal
    vote_breakdown: dict[str, dict[int, int]]
    all_critiques: list[dict]


def _collect_proposals(
    results: list[tuple[str, ProposeResponse, float]],
    proposals: list[Proposal],
    next_id: int,
) -> int:
    for model, parsed, elapsed in results:
        short = model.split("/")[-1]
        count = len(parsed.ideas)
        for idea in parsed.ideas:
            proposals.append(Proposal(
                id=next_id,
                title=idea.title,
                description=idea.description,
                rationale=idea.rationale,
                expected_impact=idea.expected_impact,
                source_model=model,
            ))
            next_id += 1
        log.info("Model %s proposed %d ideas in %.1fs", short, count, elapsed)
        print(display.model_ok(short, f"{count} ideas", elapsed))
    return next_id


def _collect_critiques(
    results: list[tuple[str, CritiqueResponse, float]],
    proposals: list[Proposal],
    all_critiques: list[dict],
) -> None:
    for model, parsed, elapsed in results:
        short = model.split("/")[-1]
        for c in parsed.critiques:
            critique_dict = c.model_dump()
            all_critiques.append(critique_dict)
            for p in proposals:
                if p.id == c.proposal_id:
                    p.critiques.append(critique_dict)
        log.info("Model %s: %d critiques in %.1fs", short, len(parsed.critiques), elapsed)
        print(display.model_ok(short, f"{len(parsed.critiques)} critiques", elapsed))
        for c in parsed.critiques:
            print(display.critique(0, c.proposal_id, c.strengths[:120], c.weaknesses[:120]))


async def run_deliberation(
    context: str,
    models: list[str],
    *,
    rounds: int = 5,
    proposals_per_model: int = 3,
    thinking: str = "extended",
) -> DeliberationResult:
    """Run the full deliberation pipeline: P → C → P → C → V."""

    proposals: list[Proposal] = []
    all_critiques: list[dict] = []
    next_id = 1

    # ── STEP 1: PROPOSE ──
    log.info("STEP 1: PROPOSE — %d models x %d ideas", len(models), proposals_per_model)
    print(display.phase("PROPOSE", f"{len(models)} models x {proposals_per_model} ideas"))
    prompt = build_propose_prompt(context, proposals_per_model)
    results = await call_all_models_typed(models, prompt, PROPOSE_TOOL, ProposeResponse)
    next_id = _collect_proposals(results, proposals, next_id)

    if not proposals:
        raise RuntimeError("No proposals received from any model")

    print()
    for p in proposals:
        print(display.proposal(p.id, p.title, p.description, p.expected_impact))
    log.info("After P1: %d proposals", len(proposals))

    # ── STEP 2: CRITIQUE 1 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 2: CRITIQUE — %d models reviewing %d proposals", len(models), len(proposals))
    print(display.phase("CRITIQUE", f"{len(models)} models reviewing {len(proposals)} proposals"))
    prompt = build_critique_prompt(context, proposals_text)
    results = await call_all_models_typed(models, prompt, CRITIQUE_TOOL, CritiqueResponse)
    _collect_critiques(results, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 3: PROPOSE 2 ──
    log.info("STEP 3: PROPOSE 2 — informed by critiques")
    print(display.phase("PROPOSE 2", f"{len(models)} models (informed by critiques)"))
    prompt = build_repropose_prompt(context, proposals_text, critiques_text, proposals_per_model)
    results = await call_all_models_typed(models, prompt, PROPOSE_TOOL, ProposeResponse)
    before_p2 = len(proposals)
    next_id = _collect_proposals(results, proposals, next_id)

    print()
    for p in proposals[before_p2:]:
        print(display.proposal(p.id, p.title, p.description, p.expected_impact))
    log.info("After P2: %d total proposals", len(proposals))

    # ── STEP 4: CRITIQUE 2 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 4: CRITIQUE 2 — %d models reviewing %d proposals", len(models), len(proposals))
    print(display.phase("CRITIQUE 2", f"{len(models)} models reviewing {len(proposals)} proposals"))
    prompt = build_critique_prompt(context, proposals_text)
    results = await call_all_models_typed(models, prompt, CRITIQUE_TOOL, CritiqueResponse)
    _collect_critiques(results, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 5: VOTE ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 5: VOTE — %d models scoring %d proposals (0-100)", len(models), len(proposals))
    print(display.phase("VOTE", f"{len(models)} models scoring {len(proposals)} proposals (0-100)"))
    prompt = build_vote_prompt(context, proposals_text, critiques_text)
    results = await call_all_models_typed(models, prompt, VOTE_TOOL, VoteResponse)

    vote_breakdown: dict[str, dict[int, int]] = {}
    for model, parsed, elapsed in results:
        short = model.split("/")[-1]
        model_votes = {}
        for v in parsed.votes:
            model_votes[v.proposal_id] = v.score
            for p in proposals:
                if p.id == v.proposal_id:
                    p.score += v.score
        vote_breakdown[model] = model_votes
        log.info("Model %s votes: %s", short, model_votes)
        print(display.model_ok(short, "voted", elapsed))

    # Sort by score, break ties randomly
    random.shuffle(proposals)
    proposals.sort(key=lambda p: p.score, reverse=True)

    # If no votes came in, just pick randomly
    if not vote_breakdown:
        log.warning("No votes received — picking random proposal")
        print(f"\n  {display.YELLOW}No votes received — picking randomly{display.RESET}")
        random.shuffle(proposals)

    # Show results
    max_possible = len(vote_breakdown) * 100 if vote_breakdown else 0
    log.info("Voting complete. Top proposals:")
    print()
    for i, p in enumerate(proposals[:5]):
        log.info("  #%d \"%s\" score=%d/%d (by %s)", i + 1, p.title, p.score, max_possible, p.source_model)
        print(display.vote_result(i + 1, p.title, p.score, max_possible))

    return DeliberationResult(
        proposals=proposals,
        winner=proposals[0],
        vote_breakdown=vote_breakdown,
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


def format_critiques_anon(critiques: list[dict]) -> str:
    parts = []
    for i, c in enumerate(critiques):
        pid = c.get("proposal_id", "?")
        parts.append(
            f"Critique {i + 1} on proposal {pid}:\n"
            f"  Strengths: {c.get('strengths', 'N/A')}\n"
            f"  Weaknesses: {c.get('weaknesses', 'N/A')}\n"
            f"  Suggestions: {c.get('suggestions', 'N/A')}"
        )
    return "\n".join(parts)
