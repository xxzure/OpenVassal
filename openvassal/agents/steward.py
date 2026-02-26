"""Steward Agent — the central orchestrator.

The Steward receives all user input and routes it to the appropriate
sub-agent via handoffs. It also handles general conversation and
provides a summary of available capabilities.

The Steward has **persistent memory**: it automatically learns and
remembers user facts (name, preferences, work context) across all
conversations, and each chat session has full conversation history.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents import Agent, handoff

from openvassal.agents.base import BaseAgent
from openvassal.config import settings

if TYPE_CHECKING:
    from openvassal.agents.registry import AgentRegistry
    from openvassal.memory import MemoryManager

logger = logging.getLogger(__name__)

# ── Default system instructions ───────────────────────────
STEWARD_INSTRUCTIONS = """\
You are **Steward**, the user's personal AI assistant.
To the user, you are the single, capable intelligence handling their requests.
Behind the scenes, you have access to specialized sub-agents. 

Your role:
1. Understand the user's request.
2. If the request requires specialized capabilities (coding, daily work, etc.), 
   silently hand off the task to the appropriate specialized sub-agent.
3. **DO NOT** tell the user you are "handing off" or "routing" them to another agent.
   Act as if you are doing the work yourself. 
4. Always be helpful, direct, and concise. Do not explain your internal architecture.

Available capabilities (via underlying sub-agents):
{agent_list}

## Memory & Personalization
You have persistent memory. You remember facts about the user across all conversations.
Pay close attention to personal details the user shares — their name, job, company,
preferences, technical skills, location, habits, family, hobbies, etc.
Use what you know to personalize your responses and be more helpful.

**What I know about you:**
{user_memory}
"""


def build_steward(
    registry: AgentRegistry,
    memory_manager: MemoryManager | None = None,
) -> Agent:
    """Build the Steward Agent with handoffs to all registered sub-agents.

    This function is called after the registry has loaded all agents,
    so we dynamically wire up handoffs based on what's available.

    Args:
        registry: The agent registry with loaded sub-agents.
        memory_manager: Optional memory manager for injecting user facts.
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

    # Inject user memory
    if memory_manager:
        user_memory = memory_manager.get_facts_text()
    else:
        user_memory = "(Memory system not active)"

    instructions = STEWARD_INSTRUCTIONS.format(
        agent_list=agent_list,
        user_memory=user_memory,
    )

    steward = Agent(
        name="Steward",
        instructions=instructions,
        model=settings.resolve_model(settings.default_model),
        handoffs=sub_agents,
    )
    return steward
