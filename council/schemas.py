"""Pydantic models and OpenRouter tool definitions for structured output."""

import copy

from pydantic import BaseModel, Field


# ── Pydantic models ──

class Idea(BaseModel):
    title: str = Field(description="Short title for the idea")
    description: str = Field(description="Detailed description of what to change")
    rationale: str = Field(description="Why this should work")
    expected_impact: str = Field(description="small, medium, or large")


class ProposeResponse(BaseModel):
    ideas: list[Idea] = Field(description="List of proposed ideas")


class Critique(BaseModel):
    proposal_id: int = Field(description="ID of the proposal being critiqued")
    strengths: str = Field(description="What's good about this proposal")
    weaknesses: str = Field(description="Risks, problems, or downsides")
    suggestions: str = Field(description="How to improve the proposal")


class CritiqueResponse(BaseModel):
    critiques: list[Critique] = Field(description="Critiques for each proposal")


class Vote(BaseModel):
    proposal_id: int = Field(description="ID of the proposal being scored")
    score: int = Field(description="Score from 0 (terrible) to 100 (excellent)", ge=0, le=100)
    reasoning: str = Field(description="Brief reason for the score")


class VoteResponse(BaseModel):
    votes: list[Vote] = Field(description="Scores for each proposal")


# ── OpenRouter tool definitions ──

def _inline_refs(schema: dict) -> dict:
    """Inline $defs references so the schema is self-contained.

    Some models (Gemini) choke on $defs/$ref. This resolves all $ref
    pointers and removes the $defs block.
    """
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})
    if not defs:
        return schema

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                if ref_name in defs:
                    return resolve(copy.deepcopy(defs[ref_name]))
                return obj
            return {k: resolve(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve(v) for v in obj]
        return obj

    return resolve(schema)


def _schema_to_tool(name: str, description: str, model_class: type[BaseModel]) -> dict:
    """Convert a Pydantic model to an OpenRouter tool definition with inlined refs."""
    schema = model_class.model_json_schema()
    schema = _inline_refs(schema)
    # Remove pydantic metadata that confuses some models
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


PROPOSE_TOOL = _schema_to_tool(
    "submit_proposals",
    "Submit your proposed ideas for improving the score",
    ProposeResponse,
)

CRITIQUE_TOOL = _schema_to_tool(
    "submit_critiques",
    "Submit your critiques of the proposals",
    CritiqueResponse,
)

VOTE_TOOL = _schema_to_tool(
    "submit_votes",
    "Submit your scores for each proposal (0-100)",
    VoteResponse,
)
