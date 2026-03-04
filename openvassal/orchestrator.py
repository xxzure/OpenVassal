"""Orchestrator — manual agent dispatch + pipeline execution.

Core orchestration module that implements:
1. Manual agent selection — user explicitly picks which agent handles a task
2. Pipeline execution — multi-step workflows where each step's output feeds
   into the next step's context
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Process, Task

from openvassal.agents.registry import AgentRegistry
from openvassal.memory import MemoryManager
from openvassal.models import PipelineConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Orchestrator:
    """Dispatches tasks to agents and executes pipelines.

    The Orchestrator is the central coordinator. Unlike the old Steward
    pattern, it does NO auto-routing — the user explicitly selects which
    agent to use, or defines a pipeline.
    """

    def __init__(self, registry: AgentRegistry, memory: MemoryManager):
        self.registry = registry
        self.memory = memory

    def run_single(
        self,
        agent_name: str,
        task_description: str,
        inject_memory: bool = True,
    ) -> str:
        """Run a single agent on a task.

        Args:
            agent_name: Name of the agent (from agents.yaml) to use.
            task_description: The user's request / task description.
            inject_memory: Whether to inject mem0 context into the task.

        Returns:
            The agent's response as a string.
        """
        agent = self.registry.get(agent_name)
        if agent is None:
            available = ", ".join(self.registry.agent_names) or "(none)"
            return f"❌ Agent '{agent_name}' not found. Available agents: {available}"

        # Inject memory context
        full_description = task_description
        if inject_memory:
            memory_context = self.memory.get_memory_context(query=task_description)
            if memory_context and memory_context != "(No relevant memories found)":
                full_description = (
                    f"{task_description}\n\n"
                    f"## Relevant Context (from your memory)\n{memory_context}"
                )

        # Create a CrewAI Task and Crew for single execution
        task = Task(
            description=full_description,
            expected_output="A helpful, detailed response to the user's request.",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        try:
            result = crew.kickoff()
            response = str(result)

            # Save interaction to mem0 (non-blocking, best-effort)
            try:
                self.memory.save_interaction(
                    user_message=task_description,
                    assistant_response=response,
                    agent_id=agent_name,
                )
            except Exception:
                logger.debug("Memory save failed (non-critical)", exc_info=True)

            return response

        except Exception as exc:
            logger.exception("Error running agent '%s'", agent_name)
            return f"⚠️ Error running {agent_name}: {exc}"

    def run_pipeline(
        self,
        pipeline_name: str,
        user_input: str,
    ) -> list[dict[str, str]]:
        """Run a multi-step pipeline.

        Each step's output is passed as context to the next step.

        Args:
            pipeline_name: Name of the pipeline (from agents.yaml).
            user_input: The user's original request.

        Returns:
            List of dicts with 'agent', 'step', and 'output' for each step.
        """
        pipeline = self.registry.get_pipeline(pipeline_name)
        if pipeline is None:
            available = ", ".join(p.name for p in self.registry.pipelines) or "(none)"
            return [{"agent": "system", "step": "error",
                      "output": f"❌ Pipeline '{pipeline_name}' not found. Available: {available}"}]

        results = []
        previous_output = ""

        for i, step in enumerate(pipeline.steps, 1):
            agent = self.registry.get(step.agent)
            if agent is None:
                results.append({
                    "agent": step.agent,
                    "step": f"Step {i}",
                    "output": f"❌ Agent '{step.agent}' not found — skipping step.",
                })
                continue

            # Build step description with context
            step_description = f"## Original User Request\n{user_input}\n\n"
            step_description += f"## Your Task (Step {i})\n{step.task}\n"

            if previous_output:
                step_description += f"\n## Output from Previous Step\n{previous_output}\n"

            # Inject memory
            memory_context = self.memory.get_memory_context(query=user_input)
            if memory_context and memory_context != "(No relevant memories found)":
                step_description += f"\n## Relevant Context (from memory)\n{memory_context}\n"

            task = Task(
                description=step_description,
                expected_output=f"Complete step {i}: {step.task}",
                agent=agent,
            )

            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )

            try:
                result = crew.kickoff()
                output = str(result)
                previous_output = output
                results.append({
                    "agent": step.agent,
                    "step": f"Step {i}: {step.task[:50]}",
                    "output": output,
                })
            except Exception as exc:
                logger.exception("Pipeline step %d failed", i)
                results.append({
                    "agent": step.agent,
                    "step": f"Step {i}: {step.task[:50]}",
                    "output": f"⚠️ Step failed: {exc}",
                })
                # Continue to next step even if one fails

        # Save the full pipeline interaction to memory
        try:
            summary = "\n\n".join(
                f"[{r['agent']}] {r['step']}:\n{r['output'][:200]}"
                for r in results
            )
            self.memory.save_interaction(
                user_message=user_input,
                assistant_response=f"Pipeline '{pipeline_name}' completed:\n{summary}",
                agent_id="pipeline",
            )
        except Exception:
            logger.debug("Pipeline memory save failed", exc_info=True)

        return results

    def get_available_agents(self) -> list[dict[str, str]]:
        """Get a list of available agents with their descriptions."""
        result = []
        for name in self.registry.agent_names:
            cfg = self.registry.get_config(name)
            result.append({
                "name": name,
                "role": cfg.role if cfg else name,
                "model": cfg.model if cfg else "",
                "goal": cfg.goal if cfg else "",
            })
        return result

    def get_available_pipelines(self) -> list[dict]:
        """Get a list of available pipelines with their descriptions."""
        result = []
        for p in self.registry.pipelines:
            result.append({
                "name": p.name,
                "description": p.description,
                "steps": [{"agent": s.agent, "task": s.task} for s in p.steps],
            })
        return result
