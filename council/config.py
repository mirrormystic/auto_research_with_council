"""Parse program.md frontmatter and council.yaml."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ChallengeConfig:
    target_file: str
    reference_files: list[str]
    validate: str
    eval: str
    metric_regex: str
    direction: str  # "maximize" or "minimize"
    program_md_raw: str  # full text including frontmatter

    @property
    def is_maximize(self) -> bool:
        return self.direction == "maximize"


@dataclass
class CouncilConfig:
    models: list[str] = field(default_factory=lambda: [
        "anthropic/claude-opus-4-6",
        "openai/gpt-5.4",
        "xai/grok-4.20",
        "google/gemini-3.1-pro",
        "deepseek/deepseek-v3.2",
    ])
    rounds: int = 3
    proposals_per_model: int = 3
    anonymous: bool = True
    tie_break: str = "random"
    thinking: str = "extended"


def parse_program_md(path: Path) -> ChallengeConfig:
    """Parse program.md with YAML frontmatter."""
    raw = path.read_text()
    if not raw.startswith("---"):
        raise ValueError(f"{path} must start with YAML frontmatter (---)")

    _, fm_str, body = raw.split("---", 2)
    fm = yaml.safe_load(fm_str)

    return ChallengeConfig(
        target_file=fm["target_file"],
        reference_files=fm.get("reference_files", []),
        validate=fm.get("validate", ""),
        eval=fm["eval"],
        metric_regex=fm["metric_regex"],
        direction=fm.get("direction", "maximize"),
        program_md_raw=raw,
    )


def load_council_config(challenge_dir: Path, overrides: dict | None = None) -> CouncilConfig:
    """Load council.yaml from challenge dir, apply CLI overrides."""
    config = CouncilConfig()
    yaml_path = challenge_dir / "council.yaml"

    if yaml_path.exists():
        data = yaml.safe_load(yaml_path.read_text()) or {}
        if "models" in data:
            config.models = data["models"]
        delib = data.get("deliberation", {})
        if "rounds" in delib:
            config.rounds = delib["rounds"]
        if "proposals_per_model" in delib:
            config.proposals_per_model = delib["proposals_per_model"]
        if "anonymous" in delib:
            config.anonymous = delib["anonymous"]
        if "tie_break" in delib:
            config.tie_break = delib["tie_break"]
        if "thinking" in data:
            config.thinking = data["thinking"]

    if overrides:
        if "models" in overrides:
            config.models = overrides["models"]
        if "rounds" in overrides:
            config.rounds = overrides["rounds"]

    return config
