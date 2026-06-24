"""
main.py — CLI entrypoint for ScholarStream AI.

Usage:
    python -m src.main
    python -m src.main --prompt "Analyze contrastive learning + GNNs for churn prediction"
    python -m src.main --demo-failure   # injects bad API key to showcase failure handling
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

from .pipeline.orchestrator import Orchestrator

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


async def stream_pipeline(prompt: str, api_key: str):
    console.print(Panel(Text(prompt, style="bold cyan"), title="📚 ScholarStream AI", expand=False))
    orch = Orchestrator(api_key=api_key)
    try:
        async for chunk in orch.run(prompt):
            console.print(chunk, end="", highlight=False)
    except Exception as exc:
        console.print(f"\n[bold red][FATAL] Pipeline crashed: {exc}[/bold red]")
        sys.exit(1)
    console.print()


def main():
    parser = argparse.ArgumentParser(description="ScholarStream AI — Agentic Research Engine")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT, help="Research query")
    parser.add_argument("--demo-failure", action="store_true", help="Inject a bad API key to demo failure handling")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    setup_logging(args.debug)

    api_key = "INVALID_KEY_FOR_DEMO" if args.demo_failure else os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[bold red]Error:[/bold red] OPENAI_API_KEY not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    asyncio.run(stream_pipeline(args.prompt, api_key))


if __name__ == "__main__":
    main()
