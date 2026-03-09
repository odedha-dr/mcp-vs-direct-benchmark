"""
MCP vs Direct vs CLI Benchmark

Usage: uv run python -m src.benchmark [--runs N] [--claude-model MODEL] [--openai-model MODEL]
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _detect_llms(claude_model: str, openai_model: str) -> dict[str, tuple[str, str]]:
    """Detect available LLMs based on API keys. Returns {label: (llm_type, model)}."""
    llms = {}
    if os.environ.get("ANTHROPIC_API_KEY"):
        llms[f"Claude ({claude_model})"] = ("anthropic", claude_model)
    if os.environ.get("OPENAI_API_KEY"):
        llms[f"GPT ({openai_model})"] = ("openai", openai_model)
    return llms


def main(
    runs: int = typer.Option(3, help="Number of runs per approach"),
    claude_model: str = typer.Option(DEFAULT_CLAUDE_MODEL, help="Claude model to use"),
    openai_model: str = typer.Option(DEFAULT_OPENAI_MODEL, help="OpenAI model to use"),
):
    """Run the MCP vs Direct vs CLI benchmark."""
    asyncio.run(_run(runs, claude_model, openai_model))


async def _run(runs: int, claude_model: str, openai_model: str):
    llms = _detect_llms(claude_model, openai_model)

    if not llms:
        console.print(
            "[bold red]No API keys found.[/bold red]\n"
            "Set ANTHROPIC_API_KEY and/or OPENAI_API_KEY in your .env file."
        )
        raise typer.Exit(1)

    console.print(f"[bold]Detected LLMs:[/bold] {', '.join(llms.keys())}")
    console.print(f"[bold]Runs per approach:[/bold] {runs}\n")

    with tempfile.TemporaryDirectory() as raw_tmp_dir:
        # Resolve symlinks (macOS /var -> /private/var) so MCP server
        # and prompt agree on the path. Avoids "access denied" errors.
        tmp_dir = str(Path(raw_tmp_dir).resolve())
        hello_path = Path(tmp_dir) / "hello.txt"
        hello_path.write_text(
            "Hello from the benchmark! This file tests read operations."
        )

        prompt = PROMPT.format(dir=tmp_dir)

        all_results = {}

        for llm_label, (llm_type, model) in llms.items():
            console.print(f"\n[bold magenta]{'=' * 60}[/bold magenta]")
            console.print(f"[bold magenta]LLM: {llm_label}[/bold magenta]")
            console.print(f"[bold magenta]{'=' * 60}[/bold magenta]")

            providers = {
                "direct": DirectToolProvider(),
                "cli": CliToolProvider(),
                "mcp (3 tools)": McpToolProvider(allowed_dirs=[tmp_dir], filter_tools=True),
                "mcp (all tools)": McpToolProvider(allowed_dirs=[tmp_dir], filter_tools=False),
            }

            llm_results = {}

            for name, provider in providers.items():
                console.print(f"\n  [bold blue]Running: {name}[/bold blue]")
                await provider.setup()
                try:
                    # Re-create hello.txt in case a previous run modified the dir
                    hello_path.write_text(
                        "Hello from the benchmark! This file tests read operations."
                    )
                    llm_results[name] = await run_benchmark(
                        provider, prompt, model=model, llm=llm_type, runs=runs
                    )
                    console.print(
                        f"    [green]Done[/green]"
                        f" — avg {llm_results[name]['avg_total_time_s']:.1f}s"
                    )
                finally:
                    await provider.teardown()

            all_results[llm_label] = llm_results

        # Format and display
        report = format_results(all_results)
        console.print(Panel(report, title="Benchmark Results", border_style="green"))

        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")

        filename = results_dir / f"benchmark-{timestamp}.md"
        filename.write_text(report)
        console.print(f"\nResults saved to [bold]{filename}[/bold]")

        # Save detailed traces for analysis
        traces = {}
        for llm_label, provider_results in all_results.items():
            traces[llm_label] = {}
            for provider_name, data in provider_results.items():
                traces[llm_label][provider_name] = {
                    "avg_api_turns": data.get("avg_api_turns"),
                    "avg_tool_calls": data.get("avg_tool_calls"),
                    "traces": data.get("traces", []),
                }

        trace_file = results_dir / f"traces-{timestamp}.json"
        trace_file.write_text(json.dumps(traces, indent=2, default=str))
        console.print(f"Traces saved to [bold]{trace_file}[/bold]")


if __name__ == "__main__":
    typer.run(main)
