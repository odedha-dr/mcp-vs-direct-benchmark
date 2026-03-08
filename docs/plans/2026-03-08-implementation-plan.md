# MCP vs Direct vs CLI Benchmark — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a benchmark comparing three tool-wiring approaches (MCP, direct Pydantic, CLI subprocess) for AI agents, measuring token overhead, latency, and end-to-end time.

**Architecture:** Three implementations of the same filesystem tools (read_file, write_file, list_directory) behind a common `ToolProvider` Protocol. A shared harness runs each through Claude's Messages API with the same prompt, collecting measurements. Results are formatted as a markdown table.

**Tech Stack:** Python 3.12+, UV, anthropic SDK, mcp SDK, pydantic, rich, typer

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/tools/__init__.py`
- Create: `src/tools/interface.py`
- Create: `src/harness/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md` (minimal placeholder)

**Step 1: Create pyproject.toml**

```toml
[project]
name = "mcp-vs-direct-benchmark"
version = "0.1.0"
description = "Benchmark: MCP vs Direct API vs CLI for AI agent tool execution"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.50.0",
    "pydantic>=2.10.0",
    "mcp>=1.0.0",
    "rich>=13.0.0",
    "typer>=0.15.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

**Step 2: Create the ToolProvider interface**

```python
# src/tools/interface.py
from typing import Protocol


class ToolProvider(Protocol):
    """Common interface for all three tool-wiring approaches."""

    async def setup(self) -> None:
        """Initialize the provider (e.g., start MCP server)."""
        ...

    async def teardown(self) -> None:
        """Clean up resources."""
        ...

    def get_tool_definitions(self) -> list[dict]:
        """Return tool definitions in Claude API format."""
        ...

    async def execute(self, name: str, params: dict) -> str:
        """Execute a tool by name, return result as string."""
        ...
```

**Step 3: Create __init__.py files, .env.example, .gitignore**

`.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

`.gitignore`:
```
__pycache__/
.env
.venv/
results/
*.egg-info/
dist/
.ruff_cache/
```

**Step 4: Initialize git repo and commit**

```bash
cd projects/personal/mcp-vs-direct-benchmark
git init
git add -A
git commit -m "chore: project scaffold with ToolProvider interface"
```

---

### Task 2: Direct API Tools (Pydantic In-Process)

**Files:**
- Create: `src/tools/direct/__init__.py`
- Create: `src/tools/direct/tools.py`
- Create: `tests/test_direct_tools.py`

**Step 1: Write the tests**

```python
# tests/test_direct_tools.py
import os
import pytest
from src.tools.direct.tools import DirectToolProvider


@pytest.fixture
def provider():
    return DirectToolProvider()


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    hello = tmp_path / "hello.txt"
    hello.write_text("Hello, world!")
    return tmp_path


async def test_list_directory(provider, tmp_benchmark_dir):
    result = await provider.execute("list_directory", {"path": str(tmp_benchmark_dir)})
    assert "hello.txt" in result


async def test_read_file(provider, tmp_benchmark_dir):
    result = await provider.execute("read_file", {"path": str(tmp_benchmark_dir / "hello.txt")})
    assert result == "Hello, world!"


async def test_write_file(provider, tmp_benchmark_dir):
    target = tmp_benchmark_dir / "output.txt"
    result = await provider.execute("write_file", {"path": str(target), "content": "written"})
    assert "success" in result.lower()
    assert target.read_text() == "written"


def test_tool_definitions(provider):
    defs = provider.get_tool_definitions()
    assert len(defs) == 3
    names = {d["name"] for d in defs}
    assert names == {"read_file", "write_file", "list_directory"}
    for d in defs:
        assert "input_schema" in d
        assert "description" in d


async def test_execute_unknown_tool(provider):
    with pytest.raises(ValueError, match="Unknown tool"):
        await provider.execute("nonexistent", {})
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_direct_tools.py -v
```
Expected: FAIL (module not found)

**Step 3: Implement DirectToolProvider**

```python
# src/tools/direct/tools.py
import os
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    path: str = Field(description="Path to the file to read")


class WriteFileInput(BaseModel):
    path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class ListDirectoryInput(BaseModel):
    path: str = Field(description="Path to the directory to list")


TOOLS = {
    "read_file": {
        "model": ReadFileInput,
        "description": "Read the contents of a file",
    },
    "write_file": {
        "model": WriteFileInput,
        "description": "Write content to a file",
    },
    "list_directory": {
        "model": ListDirectoryInput,
        "description": "List the contents of a directory",
    },
}


class DirectToolProvider:
    """In-process Pydantic tool provider. Zero serialization overhead."""

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass

    def get_tool_definitions(self) -> list[dict]:
        result = []
        for name, config in TOOLS.items():
            schema = config["model"].model_json_schema()
            # Remove Pydantic metadata not needed by Claude
            schema.pop("title", None)
            result.append({
                "name": name,
                "description": config["description"],
                "input_schema": schema,
            })
        return result

    async def execute(self, name: str, params: dict) -> str:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")

        validated = TOOLS[name]["model"](**params)

        if name == "read_file":
            return _read_file(validated.path)
        elif name == "write_file":
            return _write_file(validated.path, validated.content)
        elif name == "list_directory":
            return _list_directory(validated.path)


def _read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


def _write_file(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


def _list_directory(path: str) -> str:
    entries = os.listdir(path)
    return "\n".join(entries)
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_direct_tools.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/tools/direct/ tests/test_direct_tools.py
git commit -m "feat: direct Pydantic tool provider with tests"
```

---

### Task 3: CLI Subprocess Tools

**Files:**
- Create: `src/tools/cli/__init__.py`
- Create: `src/tools/cli/read_file.py`
- Create: `src/tools/cli/write_file.py`
- Create: `src/tools/cli/list_dir.py`
- Create: `src/tools/cli/wrapper.py`
- Create: `tests/test_cli_tools.py`

**Step 1: Write the tests**

```python
# tests/test_cli_tools.py
import pytest
from src.tools.cli.wrapper import CliToolProvider


@pytest.fixture
def provider():
    return CliToolProvider()


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    hello = tmp_path / "hello.txt"
    hello.write_text("Hello, world!")
    return tmp_path


async def test_list_directory(provider, tmp_benchmark_dir):
    result = await provider.execute("list_directory", {"path": str(tmp_benchmark_dir)})
    assert "hello.txt" in result


async def test_read_file(provider, tmp_benchmark_dir):
    result = await provider.execute("read_file", {"path": str(tmp_benchmark_dir / "hello.txt")})
    assert "Hello, world!" in result


async def test_write_file(provider, tmp_benchmark_dir):
    target = tmp_benchmark_dir / "output.txt"
    result = await provider.execute("write_file", {"path": str(target), "content": "written"})
    assert target.read_text() == "written"


def test_tool_definitions(provider):
    defs = provider.get_tool_definitions()
    assert len(defs) == 3
    names = {d["name"] for d in defs}
    assert names == {"read_file", "write_file", "list_directory"}
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli_tools.py -v
```

**Step 3: Implement standalone CLI scripts**

```python
# src/tools/cli/read_file.py
"""Standalone script: python -m src.tools.cli.read_file --path /tmp/file.txt"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    with open(args.path) as f:
        sys.stdout.write(f.read())


if __name__ == "__main__":
    main()
```

```python
# src/tools/cli/write_file.py
"""Standalone script: python -m src.tools.cli.write_file --path /tmp/file.txt --content "hello" """
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--content", required=True)
    args = parser.parse_args()
    with open(args.path, "w") as f:
        f.write(args.content)
    sys.stdout.write(f"Successfully wrote {len(args.content)} bytes to {args.path}")


if __name__ == "__main__":
    main()
```

```python
# src/tools/cli/list_dir.py
"""Standalone script: python -m src.tools.cli.list_dir --path /tmp"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    entries = os.listdir(args.path)
    sys.stdout.write("\n".join(entries))


if __name__ == "__main__":
    main()
```

**Step 4: Implement CliToolProvider wrapper**

```python
# src/tools/cli/wrapper.py
import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

TOOLS = {
    "read_file": {
        "script": "read_file.py",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file to read"}},
            "required": ["path"],
        },
    },
    "write_file": {
        "script": "write_file.py",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
    },
    "list_directory": {
        "script": "list_dir.py",
        "description": "List the contents of a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the directory to list"},
            },
            "required": ["path"],
        },
    },
}


class CliToolProvider:
    """Tool provider that executes standalone Python scripts via subprocess."""

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": config["description"],
                "input_schema": config["input_schema"],
            }
            for name, config in TOOLS.items()
        ]

    async def execute(self, name: str, params: dict) -> str:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")

        script = SCRIPT_DIR / TOOLS[name]["script"]
        cmd = [sys.executable, str(script)]
        for key, value in params.items():
            cmd.extend([f"--{key}", str(value)])

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return f"Error: {stderr.decode()}"
        return stdout.decode()
```

**Step 5: Run tests**

```bash
uv run pytest tests/test_cli_tools.py -v
```
Expected: all PASS

**Step 6: Commit**

```bash
git add src/tools/cli/ tests/test_cli_tools.py
git commit -m "feat: CLI subprocess tool provider with tests"
```

---

### Task 4: MCP Client Tools

**Files:**
- Create: `src/tools/mcp/__init__.py`
- Create: `src/tools/mcp/client.py`
- Create: `tests/test_mcp_tools.py`

**Step 1: Write the tests**

Note: MCP tests require Node.js and npx available. These are integration tests.

```python
# tests/test_mcp_tools.py
import os
import pytest
from src.tools.mcp.client import McpToolProvider


@pytest.fixture
async def provider(tmp_benchmark_dir):
    p = McpToolProvider(allowed_dirs=[str(tmp_benchmark_dir)])
    await p.setup()
    yield p
    await p.teardown()


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    hello = tmp_path / "hello.txt"
    hello.write_text("Hello, world!")
    return tmp_path


async def test_tool_definitions(provider):
    defs = provider.get_tool_definitions()
    names = {d["name"] for d in defs}
    # MCP filesystem server exposes many tools; we care about these three
    assert "read_text_file" in names or "read_file" in names
    assert "list_directory" in names
    assert "write_file" in names


async def test_list_directory(provider, tmp_benchmark_dir):
    result = await provider.execute("list_directory", {"path": str(tmp_benchmark_dir)})
    assert "hello.txt" in result


async def test_read_file(provider, tmp_benchmark_dir):
    # MCP filesystem server uses "read_text_file" not "read_file"
    result = await provider.execute("read_text_file", {"path": str(tmp_benchmark_dir / "hello.txt")})
    assert "Hello, world!" in result


async def test_write_file(provider, tmp_benchmark_dir):
    target = tmp_benchmark_dir / "output.txt"
    await provider.execute("write_file", {"path": str(target), "content": "written"})
    assert target.read_text() == "written"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mcp_tools.py -v
```

**Step 3: Implement McpToolProvider**

```python
# src/tools/mcp/client.py
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Map our canonical names to MCP server tool names
NAME_MAP = {
    "read_file": "read_text_file",
    "write_file": "write_file",
    "list_directory": "list_directory",
}
REVERSE_NAME_MAP = {v: k for k, v in NAME_MAP.items()}


class McpToolProvider:
    """Tool provider that connects to the MCP filesystem server via stdio."""

    def __init__(self, allowed_dirs: list[str]):
        self._allowed_dirs = allowed_dirs
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[dict] = []

    async def setup(self) -> None:
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", *self._allowed_dirs],
        )
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

        response = await self._session.list_tools()
        self._tools = []
        for tool in response.tools:
            self._tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            })

    async def teardown(self) -> None:
        await self._exit_stack.aclose()

    def get_tool_definitions(self) -> list[dict]:
        return self._tools

    async def execute(self, name: str, params: dict) -> str:
        if self._session is None:
            raise RuntimeError("Provider not set up. Call setup() first.")

        result = await self._session.call_tool(name, arguments=params)
        # MCP returns content as a list of content blocks
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_mcp_tools.py -v
```
Expected: all PASS (requires Node.js + npx)

**Step 5: Commit**

```bash
git add src/tools/mcp/ tests/test_mcp_tools.py
git commit -m "feat: MCP stdio tool provider with tests"
```

---

### Task 5: Benchmark Harness

**Files:**
- Create: `src/harness/__init__.py`
- Create: `src/harness/runner.py`
- Create: `src/harness/token_counter.py`
- Create: `src/harness/reporter.py`
- Create: `tests/test_harness.py`

**Step 1: Write tests for token_counter and reporter**

```python
# tests/test_harness.py
import json
from src.harness.token_counter import estimate_tokens
from src.harness.reporter import format_results


def test_estimate_tokens():
    text = "Hello, world! This is a test."
    count = estimate_tokens(text)
    assert 5 < count < 20  # rough sanity check


def test_estimate_tokens_dict():
    d = {"name": "read_file", "description": "Read a file", "input_schema": {"type": "object"}}
    count = estimate_tokens(d)
    assert count > 0


def test_format_results():
    results = {
        "direct": {
            "tool_definition_tokens": 100,
            "avg_call_latency_ms": 0.5,
            "avg_total_time_s": 3.2,
            "avg_api_input_tokens": 500,
            "avg_api_output_tokens": 200,
        },
        "cli": {
            "tool_definition_tokens": 100,
            "avg_call_latency_ms": 15.0,
            "avg_total_time_s": 4.1,
            "avg_api_input_tokens": 500,
            "avg_api_output_tokens": 200,
        },
        "mcp": {
            "tool_definition_tokens": 150,
            "avg_call_latency_ms": 25.0,
            "avg_total_time_s": 5.5,
            "avg_api_input_tokens": 550,
            "avg_api_output_tokens": 200,
        },
    }
    md = format_results(results)
    assert "direct" in md
    assert "mcp" in md
    assert "cli" in md
    assert "|" in md  # table format
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_harness.py -v
```

**Step 3: Implement token_counter.py**

```python
# src/harness/token_counter.py
import json


def estimate_tokens(data: str | dict | list) -> int:
    """Estimate token count using ~4 chars per token heuristic.

    For precise counts, use anthropic.count_tokens() — but this avoids
    an API call and is accurate enough for comparison purposes.
    """
    if isinstance(data, (dict, list)):
        text = json.dumps(data)
    else:
        text = data
    return len(text) // 4
```

**Step 4: Implement reporter.py**

```python
# src/harness/reporter.py
from datetime import datetime


def format_results(results: dict) -> str:
    """Format benchmark results as a markdown table."""
    lines = [
        f"# Benchmark Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (stdio) |",
        "|--------|-------------------|-------------------|-------------|",
    ]

    metrics = [
        ("Tool definition tokens", "tool_definition_tokens", ""),
        ("Avg tool call latency", "avg_call_latency_ms", "ms"),
        ("Avg total task time", "avg_total_time_s", "s"),
        ("Avg API input tokens", "avg_api_input_tokens", ""),
        ("Avg API output tokens", "avg_api_output_tokens", ""),
    ]

    for label, key, unit in metrics:
        direct = results["direct"][key]
        cli = results["cli"][key]
        mcp = results["mcp"][key]
        suffix = f" {unit}" if unit else ""
        lines.append(
            f"| {label} | {direct:.1f}{suffix} | {cli:.1f}{suffix} | {mcp:.1f}{suffix} |"
        )

    lines.extend([
        "",
        "## Key Takeaways",
        "",
        f"- **Token overhead**: MCP adds ~{results['mcp']['tool_definition_tokens'] - results['direct']['tool_definition_tokens']:.0f} extra tokens in tool definitions",
        f"- **Latency**: Direct is {results['mcp']['avg_call_latency_ms'] / max(results['direct']['avg_call_latency_ms'], 0.01):.0f}x faster than MCP per tool call",
        f"- **End-to-end**: Direct completes tasks in {results['direct']['avg_total_time_s']:.1f}s vs MCP's {results['mcp']['avg_total_time_s']:.1f}s",
    ])

    return "\n".join(lines)
```

**Step 5: Implement runner.py**

```python
# src/harness/runner.py
import time
import anthropic
from src.harness.token_counter import estimate_tokens


async def run_benchmark(
    provider,
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    runs: int = 3,
) -> dict:
    """Run a benchmark: send prompt to Claude with the provider's tools, measure everything."""
    client = anthropic.AsyncAnthropic()
    tool_defs = provider.get_tool_definitions()
    tool_def_tokens = estimate_tokens(tool_defs)

    all_call_latencies = []
    all_total_times = []
    all_input_tokens = []
    all_output_tokens = []

    for _ in range(runs):
        messages = [{"role": "user", "content": prompt}]
        total_input = 0
        total_output = 0
        start_time = time.perf_counter()

        while True:
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                tools=tool_defs,
                messages=messages,
            )

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                break

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    call_start = time.perf_counter()
                    result = await provider.execute(block.name, block.input)
                    call_end = time.perf_counter()
                    all_call_latencies.append((call_end - call_start) * 1000)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        total_time = time.perf_counter() - start_time
        all_total_times.append(total_time)
        all_input_tokens.append(total_input)
        all_output_tokens.append(total_output)

    return {
        "tool_definition_tokens": tool_def_tokens,
        "avg_call_latency_ms": sum(all_call_latencies) / max(len(all_call_latencies), 1),
        "avg_total_time_s": sum(all_total_times) / len(all_total_times),
        "avg_api_input_tokens": sum(all_input_tokens) / len(all_input_tokens),
        "avg_api_output_tokens": sum(all_output_tokens) / len(all_output_tokens),
    }
```

**Step 6: Run tests**

```bash
uv run pytest tests/test_harness.py -v
```
Expected: all PASS

**Step 7: Commit**

```bash
git add src/harness/ tests/test_harness.py
git commit -m "feat: benchmark harness with runner, token counter, and reporter"
```

---

### Task 6: Benchmark Entry Point

**Files:**
- Create: `src/benchmark.py`

**Step 1: Implement benchmark.py**

```python
# src/benchmark.py
"""
MCP vs Direct vs CLI Benchmark

Usage: uv run python -m src.benchmark [--runs N] [--model MODEL]
"""
import asyncio
import os
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from src.tools.direct.tools import DirectToolProvider
from src.tools.cli.wrapper import CliToolProvider
from src.tools.mcp.client import McpToolProvider
from src.harness.runner import run_benchmark
from src.harness.reporter import format_results

console = Console()

PROMPT = (
    "List the files in {dir}, read the file called hello.txt, "
    "then write a file called summary.txt containing a one-line summary of what you found."
)


def main(
    runs: int = typer.Option(3, help="Number of runs per approach"),
    model: str = typer.Option("claude-sonnet-4-20250514", help="Claude model to use"),
):
    """Run the MCP vs Direct vs CLI benchmark."""
    asyncio.run(_run(runs, model))


async def _run(runs: int, model: str):
    # Set up benchmark directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        hello_path = Path(tmp_dir) / "hello.txt"
        hello_path.write_text("Hello from the benchmark! This file tests read operations.")

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
                console.print(f"  [green]Done[/green] — avg {results[name]['avg_total_time_s']:.1f}s")
            finally:
                await provider.teardown()

        # Format and display results
        report = format_results(results)
        console.print(Panel(report, title="Benchmark Results", border_style="green"))

        # Save results
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        from datetime import datetime
        filename = results_dir / f"benchmark-{datetime.now().strftime('%Y-%m-%d-%H%M')}.md"
        filename.write_text(report)
        console.print(f"\nResults saved to [bold]{filename}[/bold]")


if __name__ == "__main__":
    typer.run(main)
```

**Step 2: Verify it runs (dry check)**

```bash
uv run python -m src.benchmark --help
```
Expected: shows help with --runs and --model options

**Step 3: Commit**

```bash
git add src/benchmark.py
git commit -m "feat: benchmark entry point with CLI options"
```

---

### Task 7: README

**Files:**
- Modify: `README.md`

**Step 1: Write the README**

The README should include:
1. **The Question** — three approaches to agent tool-wiring, which is best?
2. **Three Approaches** — brief explanation with architecture diagram (text)
3. **What We Measure** — token overhead, latency, end-to-end time
4. **Run It Yourself** — prerequisites, setup, single command
5. **Results** — placeholder table (filled in after first real run)
6. **When to Use What** — practical guidance

Keep it concise and compelling for a GitHub audience.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with methodology, setup, and run instructions"
```

---

### Task 8: First Real Benchmark Run

**Step 1: Ensure prerequisites**

```bash
node --version  # needs Node.js for MCP server
uv run python -c "import anthropic; print('OK')"
```

**Step 2: Run the benchmark**

```bash
uv run python -m src.benchmark --runs 3
```

**Step 3: Review results in `results/` and update README with actual numbers**

**Step 4: Final commit**

```bash
git add results/ README.md
git commit -m "docs: add initial benchmark results"
```
