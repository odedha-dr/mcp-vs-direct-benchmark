"""
MCP vs Direct vs CLI Benchmark

Usage: uv run python -m src.benchmark [--runs N] [--model MODEL]
"""

import asyncio
import tempfile

from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from src.harness.reporter import format_results
from src.harness.runner import run_benchmark
from src.tools.cli.wrapper import CliToolProvider
from src.tools.direct.tools import DirectToolProvider
from src.tools.mcp.client import McpToolProvider

console = Console()

PROMPT = (
    "List the files in {dir}, read the file called hello.txt, "
    "then write a file called summary.txt containing a one-line summary of what you found."
)


def main(
    runs: int = typer.Option(3, help="Number of runs per approach"),
    model: str = typer.Option(
        "claude-sonnet-4-20250514", help="Claude model to use"
    ),
):
    """Run the MCP vs Direct vs CLI benchmark."""
    asyncio.run(_run(runs, model))


async def _run(runs: int, model: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        hello_path = Path(tmp_dir) / "hello.txt"
        hello_path.write_text(
            "Hello from the benchmark! This file tests read operations."
        )

        prompt = PROMPT.format(dir=tmp_dir)

        providers = {
            "direct": DirectToolProvider(),
            "cli": CliToolProvider(),
            "mcp": McpToolProvider(allowed_dirs=[tmp_dir]),
        }

        results = {}

        for name, provider in providers.items():
            console.print(f"\n[bold blue]Running: {name}[/bold blue]")
            await provider.setup()
            try:
                results[name] = await run_benchmark(
                    provider, prompt, model=model, runs=runs
                )
                console.print(
                    f"  [green]Done[/green]"
                    f" — avg {results[name]['avg_total_time_s']:.1f}s"
                )
            finally:
                await provider.teardown()

        report = format_results(results)
        console.print(
            Panel(report, title="Benchmark Results", border_style="green")
        )

        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        filename = results_dir / (
            f"benchmark-{datetime.now().strftime('%Y-%m-%d-%H%M')}.md"
        )
        filename.write_text(report)
        console.print(f"\nResults saved to [bold]{filename}[/bold]")


if __name__ == "__main__":
    typer.run(main)
