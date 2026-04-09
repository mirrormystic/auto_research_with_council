"""Deliberation pipeline: propose → critique → propose → critique → vote."""

import random
from dataclasses import dataclass, field

from council.logger import log
from council.openrouter import call_all_models, extract_json
from council.context import build_propose_prompt, build_critique_prompt, build_vote_prompt


@dataclass
class Proposal:
    id: int
    title: str
    description: str
    rationale: str
    expected_impact: str
    source_model: str  # which model proposed it (hidden during deliberation)
    score: int = 0
    critiques: list[dict] = field(default_factory=list)


@dataclass
class DeliberationResult:
    proposals: list[Proposal]
    winner: Proposal
    vote_breakdown: dict[str, dict[int, int]]  # model -> {proposal_id: score}
    all_critiques: list[dict]


async def _collect_proposals(
    responses: list[tuple[str, str, float]],
    proposals: list[Proposal],
    next_id: int,
) -> int:
    """Parse proposals from model responses. Returns next available ID."""
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data and "ideas" in data:
            count = 0
            for idea in data["ideas"]:
                proposals.append(Proposal(
                    id=next_id,
                    title=idea.get("title", f"Idea {next_id}"),
                    description=idea.get("description", ""),
                    rationale=idea.get("rationale", ""),
                    expected_impact=idea.get("expected_impact", "medium"),
                    source_model=model,
                ))
                next_id += 1
                count += 1
            log.info("Model %s proposed %d ideas in %.1fs", short, count, elapsed)
            print(f"  ✓ {short:20s} {count} ideas ({elapsed:.1f}s)")
        else:
            log.warning("Model %s failed to return parseable proposals in %.1fs", short, elapsed)
            print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")
    return next_id


async def _collect_critiques(
    responses: list[tuple[str, str, float]],
    proposals: list[Proposal],
    all_critiques: list[dict],
) -> list[str]:
    """Parse critiques from model responses. Returns formatted critique texts."""
    critique_texts = []
    for model, text, elapsed in responses:
        short = model.split("/")[-1]
        data = extract_json(text)
        if data:
            for c in data.get("critiques", []):
                pid = c.get("proposal_id")
                # Strip reviewer identity — critiques are anonymous too
                c.pop("reviewer_model", None)
                all_critiques.append(c)
                for p in proposals:
                    if p.id == pid:
                        p.critiques.append(c)
            num_critiques = len(data.get("critiques", []))
            log.info("Model %s: %d critiques in %.1fs", short, num_critiques, elapsed)
            for c in data.get("critiques", []):
                log.info("  Critique on #%s: strengths=%s weaknesses=%s",
                         c.get("proposal_id"), c.get("strengths", "")[:150], c.get("weaknesses", "")[:150])
            # Anonymize the critique text before sharing
            critique_texts.append(text)
            print(f"  ✓ {short:20s} ({elapsed:.1f}s)")
        else:
            log.warning("Model %s failed to return parseable critiques", short)
            print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")
    return critique_texts


async def run_deliberation(
    context: str,
    models: list[str],
    *,
    rounds: int = 5,  # default: P C P C V = 5 steps
    proposals_per_model: int = 3,
    thinking: str = "extended",
) -> DeliberationResult:
    """Run the full deliberation pipeline: P → C → P → C → V."""

    proposals: list[Proposal] = []
    all_critiques: list[dict] = []
    next_id = 1
    critiques_text = ""

    # ── STEP 1: PROPOSE (initial) ──
    log.info("STEP 1: PROPOSE — %d models x %d ideas", len(models), proposals_per_model)
    print(f"\nPROPOSE  {len(models)} models x {proposals_per_model} ideas")
    prompt = build_propose_prompt(context, proposals_per_model)
    responses = await call_all_models(models, prompt, thinking=thinking)
    next_id = await _collect_proposals(responses, proposals, next_id)

    if not proposals:
        raise RuntimeError("No proposals received from any model")

    log.info("After P1: %d proposals", len(proposals))
    for p in proposals:
        log.info("  #%d [%s]: \"%s\"", p.id, p.source_model.split("/")[-1], p.title)

    # ── STEP 2: CRITIQUE 1 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 2: CRITIQUE — %d models reviewing %d proposals (anon)", len(models), len(proposals))
    print(f"\nCRITIQUE  {len(models)} models reviewing {len(proposals)} proposals")
    prompt = build_critique_prompt(context, proposals_text)
    responses = await call_all_models(models, prompt, thinking=thinking)
    critique_texts = await _collect_critiques(responses, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 3: PROPOSE 2 (informed by critiques) ──
    log.info("STEP 3: PROPOSE 2 — %d models proposing new ideas after seeing critiques", len(models))
    print(f"\nPROPOSE 2  {len(models)} models (informed by critiques)")
    prompt = build_repropose_prompt(context, proposals_text, critiques_text, proposals_per_model)
    responses = await call_all_models(models, prompt, thinking=thinking)
    next_id = await _collect_proposals(responses, proposals, next_id)

    log.info("After P2: %d total proposals", len(proposals))

    # ── STEP 4: CRITIQUE 2 ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 4: CRITIQUE 2 — %d models reviewing %d proposals (anon)", len(models), len(proposals))
    print(f"\nCRITIQUE 2  {len(models)} models reviewing {len(proposals)} proposals")
    prompt = build_critique_prompt(context, proposals_text)
    responses = await call_all_models(models, prompt, thinking=thinking)
    critique_texts_2 = await _collect_critiques(responses, proposals, all_critiques)
    critiques_text = format_critiques_anon(all_critiques)

    # ── STEP 5: VOTE ──
    proposals_text = format_proposals(proposals, anonymous=True)
    log.info("STEP 5: VOTE — %d models scoring %d proposals (0-100)", len(models), len(proposals))
    print(f"\nVOTE  {len(models)} models scoring {len(proposals)} proposals (0-100)")
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
            print(f"  ✓ {short:20s} ({elapsed:.1f}s)")
        else:
            log.warning("Model %s failed to return parseable votes", short)
            print(f"  ✗ {short:20s} failed to parse ({elapsed:.1f}s)")

    # Sort by score, break ties randomly
    random.shuffle(proposals)
    proposals.sort(key=lambda p: p.score, reverse=True)

    # Print top 3
    max_possible = len(vote_breakdown) * 100
    log.info("Voting complete. Top proposals:")
    print()
    for i, p in enumerate(proposals[:3]):
        log.info("  #%d \"%s\" score=%d/%d (by %s)", i + 1, p.title, p.score, max_possible, p.source_model)
        print(f"  #{i + 1}  \"{p.title}\"  Score: {p.score}/{max_possible}")

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
    """Format critiques without revealing who wrote them."""
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
