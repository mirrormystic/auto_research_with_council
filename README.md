# Council

Multi-model autonomous research. A committee of LLMs (Claude, GPT, Grok, Gemini, DeepSeek) brainstorm, critique, and vote on optimization ideas. The winner gets implemented and tested. Results feed back into the next round.

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch), but instead of one model iterating alone, a council of models from different providers breaks through blind spots together.

## Quick Start

```bash
# Install
uv sync

# Set your OpenRouter API key
export OPENROUTER_API_KEY=sk-or-...

# Run on the AMM challenge example
uv run council run --challenge ./examples/amm-challenge

# Or in any folder with a program.md
cd my-challenge/
uv run council run
```

## How It Works

```
PROPOSE  → 5 models each suggest 3 ideas (parallel)
CRITIQUE → each model reviews all proposals (anonymous)
VOTE     → each model scores 1-5, highest total wins
IMPLEMENT→ Claude Code writes the code change
TEST     → run evaluation, extract score
RECORD   → git commit on experiment branch with full deliberation log
REPEAT   → forever
```

## Create Your Own Challenge

See [GUIDE.md](GUIDE.md) for how to create a challenge folder, or look at `examples/amm-challenge/` for a working example.

A challenge is just a git folder with a `program.md` that has YAML frontmatter (eval command, metric regex, target file) and a markdown body describing the problem.

## Configuration

Override defaults with `council.yaml` in the challenge folder or CLI flags:

```bash
council run --models "claude-opus-4-6,gpt-5.4" --rounds 2
```
