# Council — Multi-Model Autonomous Research

## Overview

Council is a CLI tool that runs an autonomous research loop powered by a committee of LLMs from different providers. Instead of one model iterating alone (Karpathy-style), multiple models brainstorm ideas, critique each other, vote on what to try, and the winning idea gets implemented and tested. Results feed back into the next round.

The key insight: models from different providers (Claude, GPT, Grok, Gemini, DeepSeek) have genuinely different blind spots and reasoning patterns. Where one model gets stuck doing incremental variations, another breaks through with a completely different approach.

## How It Works

### Challenge Folders

Every optimization problem is defined as a git folder containing a `program.md`. This file is both the config (frontmatter) and the full problem description (body). The models see the entire file.

```
any-challenge/
├── program.md              # config + problem description
├── strategy.sol            # target file (the thing being optimized)
├── AMMStrategyBase.sol     # reference files (read-only context)
└── IAMMStrategy.sol
```

The `program.md` frontmatter defines:

```yaml
---
target_file: strategy.sol
reference_files:
  - AMMStrategyBase.sol
  - IAMMStrategy.sol
validate: "uv run amm-match validate strategy.sol"
eval: "uv run amm-match run strategy.sol"
metric_regex: "Edge: ([\\d.]+)"
direction: maximize
---
```

The body contains everything the models need: problem description, constraints, API details, scoring mechanics, key intuitions.

### The Loop

```
FOREVER:

1. CONTEXT
   - Read program.md (full file including frontmatter)
   - Read all reference files
   - Read current target file (the best version so far)
   - Gather ALL past experiments:
     git branch --list 'exp/*' | xargs git log -1 --format=...
     (score, what was tried, implementation details, which model
      proposed it, vote breakdown, critiques received)
   - Current best score

2. PROPOSE (Round 1)
   - Send context to all models in parallel via OpenRouter
   - Each model returns 3 proposals as structured JSON:
     { ideas: [{ title, description, rationale, expected_impact }] }
   - All proposals collected into a numbered list

3. CRITIQUE (Round 2)
   - Each model receives the context + all proposals (anonymous)
   - Each model comments on every proposal: strengths, weaknesses,
     risks, suggested modifications
   - Models may propose NEW ideas inspired by the discussion

4. VOTE (Round 3)
   - Each model receives context + proposals + all critiques
   - Each model scores every proposal 1-5 and returns JSON:
     { votes: [{ proposal_id, score, reasoning }] }
   - Scores summed across models
   - Ties broken randomly
   - Proposals ranked

5. IMPLEMENT
   - Winning proposal sent to Claude Code CLI:
     `claude -p "Read {target_file}. Implement this change:
      {winning_proposal_description}. Then run: {validate_command}"`
   - If validation fails, try next-ranked proposal
   - If top 3 all fail, models re-propose

6. TEST
   - Run the eval command
   - Extract score via metric_regex

7. RECORD
   - Create git branch: exp/SCORE-short-description
   - Commit with detailed message containing:
     - Score achieved
     - Which model proposed the idea (revealed post-vote)
     - Full proposal description
     - Vote breakdown (all models' scores)
     - Key critiques from other models
     - The implementation diff
   - Checkout main, loop back to step 1
```

### Models

All models accessed via OpenRouter with a single API key. Default roster:

- `anthropic/claude-opus-4-6`
- `openai/gpt-5.4`
- `xai/grok-4.20`
- `google/gemini-3.1-pro`
- `deepseek/deepseek-v3.2`

Extended thinking requested where supported.

### Configuration

Optional `council.yaml` in the challenge folder for overrides:

```yaml
models:
  - anthropic/claude-opus-4-6
  - openai/gpt-5.4
  - xai/grok-4.20
  - google/gemini-3.1-pro
  - deepseek/deepseek-v3.2

deliberation:
  rounds: 3
  proposals_per_model: 3
  anonymous: true
  tie_break: random

thinking: extended
```

### CLI

```bash
# Run in a challenge folder that has program.md:
council run

# Point to a specific challenge:
council run --challenge ./examples/amm-challenge

# Override models:
council run --models "claude-opus-4-6,gpt-5.4,grok-4.20"

# Override rounds:
council run --rounds 2
```

### Terminal Output

```
═══ COUNCIL ROUND 14 ═══  Best: 406.06

PROPOSE  5 models x 3 ideas = 15 proposals
  ✓ claude-opus-4-6    (2.1s)
  ✓ gpt-5.4            (3.8s)
  ✓ grok-4.20          (1.9s)
  ✓ gemini-3.1-pro     (3.4s)
  ✓ deepseek-v3.2      (4.7s)

CRITIQUE  5 models reviewing 15 proposals + 3 new ideas
  ✓ All critiques received

VOTE
  #1  "Estimate sigma from data, set fee = c*sigma*sqrt(k)"   Score: 21/25
  #2  "Track consecutive same-direction trades"                Score: 18/25
  #3  "Adaptive fee that decays toward 50bps over time"        Score: 14/25

IMPLEMENT  Claude Code working on #1...
  ✓ Compiled  ✓ Validated

TEST
  Running 1000 simulations...
  Score: 412.83  <- NEW BEST

RECORD -> exp/412-sigma-proportional-fee
  Proposed by: gpt-5.4
  Votes: claude=5 gpt=4 grok=4 gemini=4 deepseek=4
```

### Experiment History Format

The commit message on each experiment branch is the complete record:

```
Estimate sigma from data, set fee = c*sigma*sqrt(k) (edge: 412.83)

Proposed by: gpt-5.4 (anonymous during deliberation)
Vote breakdown: claude=5, gpt=4, grok=4, gemini=4, deepseek=4 (total: 21/25)

Description:
Instead of using a fixed EMA-to-fee mapping, estimate the per-step
volatility sigma from recent ratio changes, then set fee proportional
to sigma * sqrt(k / reserveY). This is the theoretically optimal
market maker spread for a CFMM facing GBM price process.

Key critiques:
- gemini: "Elegant but sigma estimate may be noisy with EMA. Consider
  using realized variance (squared changes) for more stable estimate."
- grok: "Similar to exp/395-optimal-spread-variants but that used
  linear scaling. The sqrt(k) term is new and might help."
- deepseek: "The constant c needs tuning. Suggest starting with c=500
  and using the fee sweep data to calibrate."

Implementation:
[diff of strategy.sol changes]
```

## Project Structure

```
auto_research_with_council/
├── council/
│   ├── __init__.py
│   ├── main.py              # CLI entry point + main loop
│   ├── config.py             # parse program.md frontmatter + council.yaml
│   ├── context.py            # build prompts from git history + files
│   ├── deliberate.py         # propose -> critique -> vote pipeline
│   ├── openrouter.py         # OpenRouter API client
│   ├── implement.py          # spawn Claude Code CLI to implement
│   ├── test.py               # run eval command, extract score
│   └── git.py                # branch, commit, log helpers
├── examples/
│   └── amm-challenge/        # working example
│       ├── program.md
│       ├── strategy.sol
│       ├── AMMStrategyBase.sol
│       └── IAMMStrategy.sol
├── GUIDE.md                  # how to create a challenge folder
├── PRD.md                    # this document
├── NEXT_FEATURES.md
├── pyproject.toml
└── README.md
```

## Tech Stack

- Python 3.12+
- OpenRouter API (single key, all models)
- Claude Code CLI (for implementation step)
- Git (experiment tracking)
- uv (package management)
- No web UI — terminal only for hackathon
