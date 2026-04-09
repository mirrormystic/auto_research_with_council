# Council

**Autonomous research, powered by a committee of LLMs.**

Council runs an optimization loop where multiple AI models (Claude, GPT, Grok, Gemini, DeepSeek) brainstorm ideas, critique each other anonymously, and vote on what to try next. The winning idea gets implemented and tested. Results feed back into the next round. It runs forever until you stop it.

The key insight: models from different providers have genuinely different blind spots. Where one model gets stuck doing incremental tweaks, another breaks through with a completely different approach.

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch), but instead of one model iterating alone, a council of models from different providers collaborates to find solutions faster.

## How It Works

```
PROPOSE   → each model suggests ideas (anonymous, parallel)
CRITIQUE  → each model reviews all proposals (anonymous)
PROPOSE 2 → models revise/combine ideas based on critiques
CRITIQUE 2→ second round of review
VOTE      → each model scores 0-100, highest total wins
IMPLEMENT → Claude Code writes the code change
TEST      → run evaluation, extract score
RECORD    → git commit with full deliberation log
REPEAT    → forever
```

Every proposal, critique, and vote uses **structured tool calling** with Pydantic validation — no fragile JSON parsing.

Each experiment is recorded as a git branch with a detailed commit message: the score, who proposed it, vote breakdown, key critiques, and the implementation diff. On every new round, the council reads all past experiments to inform its next move.

## Quick Start

```bash
# Install
uv sync
```

### Option A: Pay with Tempo MPP (no API key needed)

```bash
# Install Tempo CLI and log in (one-time)
curl -fsSL https://tempo.xyz/install | bash
tempo wallet login
tempo wallet fund

# Run the council
uv run council run --tempo \
  --models "anthropic/claude-sonnet-4-6,openai/gpt-4o,google/gemini-2.5-pro" \
  --challenge ./examples/amm-challenge
```

### Option B: Pay with OpenRouter API key

```bash
uv run council run --openrouter-key sk-or-v1-... \
  --models "anthropic/claude-sonnet-4-6,openai/gpt-4o,google/gemini-2.5-pro" \
  --challenge ./examples/amm-challenge
```

### CLI Options

```
--tempo                Pay via Tempo MPP
--openrouter-key KEY   Pay via OpenRouter API key
--models MODELS        Comma-separated model list (required)
--challenge PATH       Path to challenge folder (default: current dir)
--rounds N             Number of deliberation rounds (default: 3)
```

### Example Commands

```bash
# Quick test with 2 cheap models
uv run council run --tempo \
  --models "openai/gpt-4o-mini,google/gemini-2.0-flash-001" \
  --challenge ./examples/amm-challenge

# Full council with 4 frontier models
uv run council run --tempo \
  --models "anthropic/claude-sonnet-4-6,openai/gpt-4o,google/gemini-2.5-pro,deepseek/deepseek-v3.2" \
  --challenge ./examples/amm-challenge

# Fewer deliberation rounds (faster, less thorough)
uv run council run --tempo --rounds 2 \
  --models "anthropic/claude-sonnet-4-6,openai/gpt-4o" \
  --challenge ./examples/amm-challenge

# Verbose logging (see everything on screen)
COUNCIL_LOG_LEVEL=DEBUG uv run council run --tempo \
  --models "openai/gpt-4o-mini" \
  --challenge ./examples/amm-challenge
```

## Create Your Own Challenge

A challenge is a git folder with a `program.md`. The frontmatter defines the mechanics, the body describes the problem:

```yaml
---
target_file: train.py
reference_files: [utils.py]
validate: "python -c 'import train'"
eval: "python train.py"
metric_regex: "val_loss: ([\\d.]+)"
direction: minimize
---

# My Optimization Problem

Describe the problem here. The models see this entire file...
```

See [GUIDE.md](GUIDE.md) for details or `examples/amm-challenge/` for a working example.

## Architecture

- **Structured output**: Pydantic schemas → OpenRouter tool calling → validated typed responses. No regex, no prayer.
- **Anonymous deliberation**: Models don't know who proposed what during critique and voting. Proposer revealed only in the commit message after scoring.
- **Payment flexibility**: `--tempo` pays via [Tempo MPP](https://mpp.dev) (HTTP 402 auto-payment), `--openrouter-key` uses a standard API key.
- **Git as state**: Stop and restart anytime. The council reads all `exp/*` branches on startup and picks up where it left off.
- **Full audit trail**: `council.log` captures every API call, response, and decision at DEBUG level. Set `COUNCIL_LOG_LEVEL=DEBUG` to see it on screen.

## Built With

- [OpenRouter](https://openrouter.ai) — unified API for all models
- [Tempo MPP](https://mpp.dev) — machine-to-machine payments (optional)
- [Pydantic](https://pydantic.dev) — structured output validation
- [Claude Code](https://claude.ai/code) — implementation agent

## License

MIT
