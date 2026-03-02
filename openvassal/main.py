"""CLI entry point — OpenVassal interactive personal assistant."""

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

from openvassal.agents.registry import AgentRegistry
from openvassal.agents.steward import build_steward
from openvassal.config import settings
from openvassal.memory import MemoryManager

console = Console()
logger = logging.getLogger("openvassal")


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-25s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_banner(registry: AgentRegistry) -> None:
    agents = ", ".join(registry.agent_names) or "(none)"
    console.print(
        Panel.fit(
            f"[bold cyan]OpenVassal[/] — AI Personal Assistant\n\n"
            f"[dim]Model:[/]  {settings.default_model}\n"
            f"[dim]Agents:[/] {agents}\n"
            f"\n"
            f"[dim]Type your request, or /help for commands.[/]",
            border_style="cyan",
        )
    )


async def _run_loop() -> None:
    """Main REPL loop."""
    # Load the system
    registry = AgentRegistry()
    registry.load()

    # Initialize memory
    memory_mgr = MemoryManager()
    conv = memory_mgr.create_conversation("CLI Session")
    session = memory_mgr.get_or_create_session(conv["id"])

    steward = build_steward(registry, memory_manager=memory_mgr)

    _print_banner(registry)

    facts = memory_mgr.get_all_facts()
    if facts:
        console.print(f"[dim]Memory:[/] {len(facts)} facts remembered about you")

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input.strip():
            continue

        # ── Slash commands ────────────────────────────
        cmd = user_input.strip().lower()
        if cmd in ("/quit", "/exit", "/q"):
            console.print("[dim]Goodbye![/]")
            break
        if cmd == "/help":
            console.print(
                Markdown(
                    "**Commands:**\n"
                    "- `/agents` — list loaded agents\n"
                    "- `/memory` — show remembered facts\n"
                    "- `/quit` — exit\n"
                )
            )
            continue
        if cmd == "/agents":
            for name, agent in registry.get_all().items():
                console.print(f"  [cyan]{name}[/] — {agent.description}")
            continue
        if cmd == "/memory":
            facts = memory_mgr.get_all_facts()
            if facts:
                console.print(Panel(
                    "\n".join(f"• {f['fact']}" for f in facts),
                    title="🧠 What I Remember",
                    border_style="magenta",
                ))
            else:
                console.print("[dim]No facts remembered yet. Keep chatting![/]")
            continue

        # ── Run the Steward ───────────────────────────
        with console.status("[bold cyan]Thinking…[/]"):
            try:
                result = await Runner.run(steward, input=user_input, session=session)
                response = result.final_output
            except Exception as exc:
                logger.exception("Error running agent")
                response = f"⚠️  Something went wrong: {exc}"

        console.print(f"\n[bold blue]Steward[/]")
        console.print(Markdown(response))

        # ── Extract and save facts (background, non-blocking) ──
        memory_mgr.touch_conversation(conv["id"])
        try:
            await memory_mgr.extract_and_save_facts(
                user_message=user_input,
                assistant_response=response,
                session_id=conv["id"],
            )
            # Rebuild steward with updated facts for next turn
            steward = build_steward(registry, memory_manager=memory_mgr)
        except Exception:
            logger.debug("Fact extraction failed (non-critical)", exc_info=True)


def cli() -> None:
    """Entry point registered in pyproject.toml."""
    parser = argparse.ArgumentParser(description="OpenVassal — AI Personal Assistant")
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
        from openvassal.web.server import start_server

        url = f"http://127.0.0.1:{args.port}"
        console.print(
            Panel.fit(
                f"[bold cyan]OpenVassal Setup[/]\n\n"
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
