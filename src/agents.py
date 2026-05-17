from agents import Agent, Runner

from .file_store import read_text
from .settings import AGENT_INSTRUCTIONS_DIR, OPENAI_MODEL


def load_instruction(name: str) -> str:
    return read_text(AGENT_INSTRUCTIONS_DIR / f"{name}.md")


def build_agent(name: str, instruction_file: str) -> Agent:
    return Agent(
        name=name,
        instructions=load_instruction(instruction_file),
        model=OPENAI_MODEL,
    )


async def run_agent(agent: Agent, prompt: str) -> str:
    result = await Runner.run(agent, prompt)
    return result.final_output


content_strategist_agent = build_agent("Content Strategist", "content_strategist")
content_creator_agent = build_agent("Content Creator", "content_creator")
content_candidate_agent = build_agent("Content Candidate Planner", "content_candidate")
creative_composer_agent = build_agent("Creative Composition Art Director", "creative_composer")
seo_agent = build_agent("SEO Agent", "seo")
analytics_agent = build_agent("Analytics Agent", "analytics")
ad_strategist_agent = build_agent("Future Ad Strategist", "ad_strategist")
visual_designer_agent = build_agent("Visual Designer", "visual_designer")
feed_curator_agent = build_agent("Feed Curator", "feed_curator")
orchestrator_agent = build_agent("Growth Orchestrator", "orchestrator")
