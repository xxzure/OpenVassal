"""CLI entry point — interactive personal assistant."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import webbrowser

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from agents import Runner

from subordinates.agents.registry import AgentRegistry
from subordinates.agents.steward import build_steward
from subordinates.config import settings
from subordinates.plans.manager import PlanManager

console = Console()
logger = logging.getLogger("subordinates")


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-25s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_banner(registry: AgentRegistry, plan_mgr: PlanManager) -> None:
    agents = ", ".join(registry.agent_names) or "(none)"
    console.print(
        Panel.fit(
            f"[bold cyan]Subordinates[/] — AI Personal Assistant\n\n"
            f"[dim]Model:[/]  {settings.default_model}\n"
            f"[dim]Agents:[/] {agents}\n"
            f"[dim]Plan:[/]   {plan_mgr.subscription.base_plan} "
            f"(${plan_mgr.monthly_total:.2f}/mo)\n\n"
            f"[dim]Type your request, or /help for commands.[/]",
            border_style="cyan",
        )
    )


async def _run_loop() -> None:
    """Main REPL loop."""
    # Load the system
    registry = AgentRegistry()
    registry.load()

    plan_mgr = PlanManager()
    plan_mgr.subscription.base_plan = "base"
    for name in registry.agent_names:
        plan_mgr.add_agent_plan(name)

    steward = build_steward(registry)

    _print_banner(registry, plan_mgr)

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input.strip():
            continue

        # ── Slash commands ────────────────────────────────
        cmd = user_input.strip().lower()
        if cmd in ("/quit", "/exit", "/q"):
            console.print("[dim]Goodbye![/]")
            break
        if cmd == "/help":
            console.print(
                Markdown(
                    "**Commands:**\n"
                    "- `/plan` — show subscription info\n"
                    "- `/agents` — list loaded agents\n"
                    "- `/quit` — exit\n"
                )
            )
            continue
        if cmd == "/plan":
            console.print(Panel(plan_mgr.summary(), title="Subscription", border_style="yellow"))
            continue
        if cmd == "/agents":
            for name, agent in registry.get_all().items():
                console.print(f"  [cyan]{name}[/] — {agent.description}")
            continue

        # ── Run the Steward ───────────────────────────────
        with console.status("[bold cyan]Thinking…[/]"):
            try:
                result = await Runner.run(steward, input=user_input)
                response = result.final_output
            except Exception as exc:
                logger.exception("Error running agent")
                response = f"⚠️  Something went wrong: {exc}"

        console.print(f"\n[bold blue]Steward[/]")
        console.print(Markdown(response))


def cli() -> None:
    """Entry point registered in pyproject.toml."""
    parser = argparse.ArgumentParser(description="Subordinates — AI Personal Assistant")
    parser.add_argument(
        "--setup", action="store_true",
        help="Launch the web-based configuration UI",
    )
    parser.add_argument(
        "--port", type=int, default=8585,
        help="Port for the setup UI (default: 8585)",
    )
    args = parser.parse_args()

    _setup_logging()

    if args.setup:
        from subordinates.web.server import start_server

        url = f"http://127.0.0.1:{args.port}"
        console.print(
            Panel.fit(
                f"[bold cyan]Subordinates Setup[/]\n\n"
                f"Open [link={url}]{url}[/link] in your browser.\n"
                f"Press [bold]Ctrl+C[/] to stop.",
                border_style="cyan",
            )
        )
        webbrowser.open(url)
        start_server(port=args.port)
        return

    try:
        asyncio.run(_run_loop())
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")
        sys.exit(0)


if __name__ == "__main__":
    cli()
