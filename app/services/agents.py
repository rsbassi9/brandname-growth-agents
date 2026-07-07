"""Port of src/agents.py agent construction (P1-3).

Signatures preserved (load_instruction, build_agent, run_agent). Two changes:
- agents are built lazily via get_agent() instead of at import time;
- run_agent() goes through the local-only guard so no execution path can reach
  OpenAI while LOCAL_ONLY_AGENT_RUNS=true.
"""

from __future__ import annotations

from typing import Any

from ..paths import agent_instructions_dir
from .files import read_text
from .openai_client import ensure_external_calls_allowed, resolve_model

AGENT_SPECS: dict[str, tuple[str, str]] = {
    "content_strategist": ("Content Strategist", "content_strategist"),
    "content_creator": ("Content Creator", "content_creator"),
    "content_candidate": ("Content Candidate Planner", "content_candidate"),
    "creative_composer": ("Creative Composition Art Director", "creative_composer"),
    "seo": ("SEO Agent", "seo"),
    "analytics": ("Analytics Agent", "analytics"),
    "ad_strategist": ("Future Ad Strategist", "ad_strategist"),
    "visual_designer": ("Visual Designer", "visual_designer"),
    "feed_curator": ("Feed Curator", "feed_curator"),
    "orchestrator": ("Growth Orchestrator", "orchestrator"),
}

_agent_cache: dict[str, Any] = {}


def load_instruction(name: str) -> str:
    return read_text(agent_instructions_dir() / f"{name}.md")


def build_agent(name: str, instruction_file: str, premium: bool = False) -> Any:
    from agents import Agent

    return Agent(
        name=name,
        instructions=load_instruction(instruction_file),
        model=resolve_model(premium=premium),
    )


def get_agent(key: str, premium: bool = False) -> Any:
    if key not in AGENT_SPECS:
        raise KeyError(f"Unknown agent key: {key}")
    cache_key = f"{key}:premium" if premium else key
    if cache_key not in _agent_cache:
        name, instruction_file = AGENT_SPECS[key]
        _agent_cache[cache_key] = build_agent(name, instruction_file, premium=premium)
    return _agent_cache[cache_key]


def reset_agent_cache() -> None:
    _agent_cache.clear()


async def run_agent(agent: Any, prompt: str) -> str:
    # Raises LocalOnlyModeError before any network call in local-only mode.
    ensure_external_calls_allowed()
    from agents import Runner

    result = await Runner.run(agent, prompt)
    return result.final_output
