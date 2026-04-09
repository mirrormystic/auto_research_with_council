"""Deliberation pipeline: propose → critique → propose → critique → vote."""

import random
from dataclasses import dataclass, field

from council.logger import log
from council.openrouter import call_all_models, extract_json
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


async def _collect_proposals(
    responses: list[tuple[str, str, float]],
    proposals: list[Proposal],
    next_id: int,
) -> int:
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data and "ideas" in data:
            count = 0
            for idea in data["ideas"]:
                p = Proposal(
                    id=next_id,
                    title=idea.get("title", f"Idea {next_id}"),
                    description=idea.get("description", ""),
                    rationale=idea.get("rationale", ""),
                    expected_impact=idea.get("expected_impact", "medium"),
                    source_model=model,
                )
                proposals.append(p)
                next_id += 1
                count += 1
            log.info("Model %s proposed %d ideas in %.1fs", short, count, elapsed)
            print(display.model_ok(short, f"{count} ideas", elapsed))
        else:
            log.warning("Model %s failed to parse in %.1fs", short, elapsed)
            print(display.model_fail(short, "failed to parse"))
    return next_id


async def _collect_critiques(
    responses: list[tuple[str, str, float]],
    proposals: list[Proposal],
    all_critiques: list[dict],
) -> None:
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data:
            for c in data.get("critiques", []):
                pid = c.get("proposal_id")
                c.pop("reviewer_model", None)
                all_critiques.append(c)
                for p in proposals:
                    if p.id == pid:
                        p.critiques.append(c)
            num_critiques = len(data.get("critiques", []))
            log.info("Model %s: %d critiques in %.1fs", short, num_critiques, elapsed)
            print(display.model_ok(short, f"{num_critiques} critiques", elapsed))
            # Show critiques
            for c in data.get("critiques", []):
                pid = c.get("proposal_id", "?")
                print(display.critique(0, pid,
                    c.get("strengths", "")[:120],
                    c.get("weaknesses", "")[:120]))
        else:
            log.warning("Model %s failed to parse critiques", short)
            print(display.model_fail(short, "failed to parse"))


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
    responses = await call_all_models(models, prompt, thinking=thinking)
    next_id = await _collect_proposals(responses, proposals, next_id)

    if not proposals:
        raise RuntimeError("No proposals received from any model")

    # Show proposals
    print()
    for p in proposals:
        print(display.proposal(p.id, p.title, p.description, p.expected_impact))
    log.info("After P1: %d proposals", len(proposals))

    # ── STEP 2: CRITIQUE 1 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 2: CRITIQUE — %d models reviewing %d proposals", len(models), len(proposals))
    print(display.phase("CRITIQUE", f"{len(models)} models reviewing {len(proposals)} proposals"))
    prompt = build_critique_prompt(context, proposals_text)
    responses = await call_all_models(models, prompt, thinking=thinking)
    await _collect_critiques(responses, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 3: PROPOSE 2 ──
    log.info("STEP 3: PROPOSE 2 — informed by critiques")
    print(display.phase("PROPOSE 2", f"{len(models)} models (informed by critiques)"))
    prompt = build_repropose_prompt(context, proposals_text, critiques_text, proposals_per_model)
    responses = await call_all_models(models, prompt, thinking=thinking)
    next_id = await _collect_proposals(responses, proposals, next_id)

    # Show new proposals
    print()
    for p in proposals:
        if p.id >= next_id - len(responses) * proposals_per_model:
            print(display.proposal(p.id, p.title, p.description, p.expected_impact))
    log.info("After P2: %d total proposals", len(proposals))

    # ── STEP 4: CRITIQUE 2 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 4: CRITIQUE 2 — %d models reviewing %d proposals", len(models), len(proposals))
    print(display.phase("CRITIQUE 2", f"{len(models)} models reviewing {len(proposals)} proposals"))
    prompt = build_critique_prompt(context, proposals_text)
    responses = await call_all_models(models, prompt, thinking=thinking)
    await _collect_critiques(responses, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 5: VOTE ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 5: VOTE — %d models scoring %d proposals (0-100)", len(models), len(proposals))
    print(display.phase("VOTE", f"{len(models)} models scoring {len(proposals)} proposals (0-100)"))
    prompt = build_vote_prompt(context, proposals_text, critiques_text)
    responses = await call_all_models(models, prompt, thinking=thinking)

    vote_breakdown: dict[str, dict[int, int]] = {}
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data and "votes" in data:
            model_votes = {}
            for v in data["votes"]:
                pid = v.get("proposal_id")
                score = min(100, max(0, int(v.get("score", 50))))
                model_votes[pid] = score
                for p in proposals:
                    if p.id == pid:
                        p.score += score
            vote_breakdown[model] = model_votes
            log.info("Model %s votes: %s", short, model_votes)
            print(display.model_ok(short, "voted", elapsed))
        else:
            log.warning("Model %s failed to parse votes", short)
            print(display.model_fail(short, "failed to parse votes"))

    # Sort by score, break ties randomly
    random.shuffle(proposals)
    proposals.sort(key=lambda p: p.score, reverse=True)

    # Show results
    max_possible = len(vote_breakdown) * 100
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
