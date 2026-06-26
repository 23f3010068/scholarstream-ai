"""
    python -m src.main
    python -m src.main --prompt "Your research query here"
    python -m src.main --demo-failure
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .pipeline.graph import build_graph

load_dotenv()
console = Console()

DEFAULT_PROMPT = (
    "Analyze the intersection of contrastive learning and graph neural networks "
    "for customer churn prediction. Find relevant paper concepts, extract architectural "
    "constraints, outline a novel architecture, and write an abstract."
)


def setup_logging(debug: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )


async def run_pipeline(prompt: str, api_key: str):
    graph = build_graph(api_key=api_key)
    initial_state = {
        "user_prompt":      prompt,
        "tasks":            [],
        "retriever_output": "",
        "analyzer_output":  "",
        "writer_output":    "",
        "errors":           [],
        "stream_log":       [],
    }
    try:
        # LangGraph streams state deltas after each node completes
        async for event in graph.astream(initial_state):
            node_name = list(event.keys())[0]
            node_output = event[node_name]
            logs = node_output.get("stream_log", [])
            for log in logs:
                console.print(f"  ✓ {log}", style="dim green")
    except Exception as exc:
        console.print(f"\n[bold red][FATAL] Pipeline crashed: {exc}[/bold red]")
        sys.exit(1)

    console.print("\n[bold green] Pipeline complete.[/bold green]")


def main():
    parser = argparse.ArgumentParser(description="ScholarStream AI — LangGraph Research Engine")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--demo-failure", action="store_true", help="Inject bad API key to demo failure handling")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    setup_logging(args.debug)
    api_key = "INVALID_KEY_FOR_DEMO" if args.demo_failure else os.getenv("GROQ_API_KEY", "")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GROQ_API_KEY not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    console.print(Panel(Text(args.prompt, style="bold cyan"), title="📚 ScholarStream AI (LangGraph)", expand=False))
    asyncio.run(run_pipeline(args.prompt, api_key))


if __name__ == "__main__":
    main()
