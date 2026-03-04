"""CLI entry point — OpenVassal interactive personal assistant.

Supports:
- Manual agent selection: /use <agent_name>
- Pipeline execution: /pipeline <name> <description>
- Memory views: /memory, /memory search <query>
- Standard chat with the currently selected agent
"""

from __future__ import annotations

import argparse
import logging
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from openvassal.agents.registry import AgentRegistry
from openvassal.config import settings
from openvassal.memory import MemoryManager
from openvassal.orchestrator import Orchestrator

console = Console()
logger = logging.getLogger("openvassal")


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-25s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_banner(registry: AgentRegistry, active_agent: str) -> None:
    agents = ", ".join(registry.agent_names) or "(none)"
    pipelines = ", ".join(p.name for p in registry.pipelines) or "(none)"
    console.print(
        Panel.fit(
            f"[bold cyan]OpenVassal[/] — Personal Knowledge Base\n\n"
            f"[dim]Active Agent:[/]  [bold green]{active_agent}[/]\n"
            f"[dim]Agents:[/]        {agents}\n"
            f"[dim]Pipelines:[/]     {pipelines}\n"
            f"\n"
            f"[dim]Type your request, or /help for commands.[/]",
            border_style="cyan",
        )
    )


def _print_help() -> None:
    console.print(
        Markdown(
            "## Commands\n"
            "- `/use <agent>` — switch to a different agent\n"
            "- `/agents` — list available agents\n"
            "- `/pipeline <name> <description>` — run a multi-step pipeline\n"
            "- `/pipelines` — list available pipelines\n"
            "- `/memory` — show all memories\n"
            "- `/memory search <query>` — search memories\n"
            "- `/help` — show this help\n"
            "- `/quit` — exit\n"
        )
    )


def _run_loop() -> None:
    """Main REPL loop."""
    registry = AgentRegistry()
    registry.load()

    memory = MemoryManager()
    orchestrator = Orchestrator(registry, memory)

    # Determine initial agent
    active_agent = settings.default_agent
    if not active_agent or active_agent not in registry.agent_names:
        active_agent = registry.agent_names[0] if registry.agent_names else ""

    _print_banner(registry, active_agent)

    # Show memory count
    memories = memory.get_all_memories()
    if memories:
        console.print(f"[dim]Memory:[/] {len(memories)} memories loaded")

    while True:
        try:
            prompt_label = f"\n[bold green]You[/] [dim]→ {active_agent}[/]"
            user_input = Prompt.ask(prompt_label)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip()
        cmd_lower = cmd.lower()

        # ── Slash commands ────────────────────────────
        if cmd_lower in ("/quit", "/exit", "/q"):
            console.print("[dim]Goodbye![/]")
            break

        if cmd_lower == "/help":
            _print_help()
            continue

        if cmd_lower == "/agents":
            table = Table(title="Available Agents", border_style="cyan")
            table.add_column("Name", style="cyan bold")
            table.add_column("Role")
            table.add_column("Model", style="dim")
            for info in orchestrator.get_available_agents():
                marker = " ◀" if info["name"] == active_agent else ""
                table.add_row(
                    f"{info['name']}{marker}",
                    info["role"],
                    info["model"],
                )
            console.print(table)
            continue

        if cmd_lower.startswith("/use "):
            new_agent = cmd[5:].strip()
            if new_agent in registry.agent_names:
                active_agent = new_agent
                cfg = registry.get_config(active_agent)
                role = cfg.role if cfg else ""
                console.print(f"[green]✔[/] Switched to [bold cyan]{active_agent}[/] ({role})")
            else:
                available = ", ".join(registry.agent_names)
                console.print(f"[red]Agent '{new_agent}' not found.[/] Available: {available}")
            continue

        if cmd_lower == "/pipelines":
            table = Table(title="Available Pipelines", border_style="magenta")
            table.add_column("Name", style="magenta bold")
            table.add_column("Description")
            table.add_column("Steps", style="dim")
            for p in orchestrator.get_available_pipelines():
                steps_str = " → ".join(s["agent"] for s in p["steps"])
                table.add_row(p["name"], p["description"], steps_str)
            console.print(table)
            continue

        if cmd_lower.startswith("/pipeline "):
            parts = cmd[10:].strip().split(" ", 1)
            pipeline_name = parts[0]
            user_request = parts[1] if len(parts) > 1 else ""
            if not user_request:
                console.print("[yellow]Usage: /pipeline <name> <description>[/]")
                continue

            console.print(f"\n[bold magenta]Pipeline:[/] {pipeline_name}")
            with console.status("[bold magenta]Running pipeline…[/]"):
                results = orchestrator.run_pipeline(pipeline_name, user_request)

            for r in results:
                console.print(f"\n[bold blue]{r['agent']}[/] — {r['step']}")
                console.print(Markdown(r["output"]))
            continue

        if cmd_lower == "/memory":
            memories = memory.get_all_memories()
            if memories:
                lines = []
                for m in memories:
                    text = m.get("memory", m.get("text", str(m)))
                    mid = m.get("id", "?")
                    lines.append(f"• {text}  [dim](id: {mid})[/]")
                console.print(Panel(
                    "\n".join(lines),
                    title="🧠 Memories",
                    border_style="magenta",
                ))
            else:
                console.print("[dim]No memories yet. Keep chatting![/]")
            continue

        if cmd_lower.startswith("/memory search "):
            query = cmd[15:].strip()
            results = memory.search_memory(query)
            if results:
                lines = []
                for m in results:
                    text = m.get("memory", m.get("text", str(m)))
                    score = m.get("score", "")
                    score_str = f" (score: {score:.2f})" if score else ""
                    lines.append(f"• {text}{score_str}")
                console.print(Panel(
                    "\n".join(lines),
                    title=f"🔍 Search: {query}",
                    border_style="blue",
                ))
            else:
                console.print(f"[dim]No memories found for '{query}'[/]")
            continue

        # ── Run the active agent ──────────────────────
        if not active_agent:
            console.print("[red]No agent selected. Use /use <agent_name> to select one.[/]")
            continue

        with console.status(f"[bold cyan]{active_agent} is thinking…[/]"):
            response = orchestrator.run_single(active_agent, cmd)

        console.print(f"\n[bold blue]{active_agent}[/]")
        console.print(Markdown(response))


def cli() -> None:
    """Entry point registered in pyproject.toml."""
    parser = argparse.ArgumentParser(description="OpenVassal — Personal Knowledge Base")
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
        import webbrowser

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
        _run_loop()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")
        sys.exit(0)


if __name__ == "__main__":
    cli()
