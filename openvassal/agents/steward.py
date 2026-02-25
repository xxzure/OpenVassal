"""Steward Agent — the central orchestrator.

The Steward receives all user input and routes it to the appropriate
sub-agent via handoffs. It also handles general conversation and
provides a summary of available capabilities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents import Agent, handoff

from openvassal.agents.base import BaseAgent
from openvassal.config import settings

if TYPE_CHECKING:
    from openvassal.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)

# ── Default system instructions ───────────────────────────
STEWARD_INSTRUCTIONS = """\
You are **Steward**, the user's personal AI assistant orchestrator.

Your role:
1. Understand the user's request.
2. If you can answer directly (greetings, general questions), do so.
3. If the request requires a specialist, hand off to the appropriate agent.
4. Always be helpful, concise, and friendly.

Available sub-agents:
{agent_list}

When handing off, briefly explain to the user which agent you're routing them to.
If no sub-agent is suitable, handle the request yourself.
"""


def build_steward(registry: AgentRegistry) -> Agent:
    """Build the Steward Agent with handoffs to all registered sub-agents.

    This function is called after the registry has loaded all agents,
    so we dynamically wire up handoffs based on what's available.
    """
    # Build SDK Agent instances for each registered sub-agent
    sub_agents = []
    agent_descriptions = []

    for name, base_agent in registry.get_all().items():
        try:
            sdk_agent = base_agent.build_agent()
            sub_agents.append(sdk_agent)
            agent_descriptions.append(f"- **{name}**: {base_agent.description}")
            logger.info("Steward: wired handoff → %s", name)
        except Exception:
            logger.exception("Steward: failed to build agent '%s'", name)

    # Build instructions with the dynamic agent list
    agent_list = "\n".join(agent_descriptions) if agent_descriptions else "- (no sub-agents loaded)"
    instructions = STEWARD_INSTRUCTIONS.format(agent_list=agent_list)

    steward = Agent(
        name="Steward",
        instructions=instructions,
        model=settings.default_model,
        handoffs=sub_agents,
    )
    return steward
