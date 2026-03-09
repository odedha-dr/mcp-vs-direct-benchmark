# MCP vs Direct vs CLI Benchmark

**Benchmarking three approaches to wiring tools into AI agents — so you can pick the right one.**

## The Question

When building AI agents, how should tools be connected to the LLM? MCP (Model Context Protocol) is the emerging standard for tool integration, but it introduces protocol overhead: server lifecycle, JSON-RPC serialization, and dynamic discovery. Is that overhead worth it when your tools run in the same process? This benchmark measures the concrete cost of each approach across latency, token usage, and end-to-end task completion.

## Three Approaches

### MCP (Model Context Protocol)

Spawns a server process, connects via stdio JSON-RPC, and discovers tools dynamically at runtime. This is the standard for cross-boundary tool communication — ideal when tools live in separate processes, machines, or are provided by third parties.

### Direct API (Pydantic)

In-process Python functions with Pydantic models for input validation. Tool schemas are generated from `model_json_schema()` and passed directly to the Anthropic API. Zero serialization overhead, zero process boundaries.

### CLI (subprocess)

Standalone Python scripts invoked via `asyncio.create_subprocess_exec`. Each tool is an independently runnable script that accepts JSON on stdin and returns JSON on stdout. The agent shells out for every call.

## What We Measure

| Metric | Description |
|--------|-------------|
| **Token overhead** | Size of tool definitions sent in each API request |
| **Per-call latency** | Wall-clock time from tool invocation to result |
| **End-to-end task time** | Total time to complete a multi-step agent task |
| **Total API tokens** | Input + output tokens consumed across the full task |

All three approaches execute the same task (file operations in a temp directory) with the same underlying tool implementations, so differences reflect pure integration overhead.

## Run It Yourself

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js (required by MCP server runtime)
- Anthropic API key and/or OpenAI API key

### Setup

```bash
git clone https://github.com/odedha-dr/mcp-vs-direct-benchmark.git
cd mcp-vs-direct-benchmark

cp .env.example .env
# Add ANTHROPIC_API_KEY and/or OPENAI_API_KEY to .env

uv sync --group dev
```

### Run

```bash
uv run python -m src.benchmark           # default: 3 runs per approach
uv run python -m src.benchmark --runs 2  # faster: 2 runs
```

The benchmark auto-detects which API keys are present and runs Claude, GPT, or both.

```bash
# Override models
uv run python -m src.benchmark --claude-model claude-sonnet-4-20250514 --openai-model gpt-4o-mini
```

Results are printed to the terminal and saved to `results/`.

## Results

Benchmark run on 2026-03-09, 2 runs per approach, same filesystem task (list directory, read file, write summary file).

### Claude (Sonnet 4)

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (stdio) |
|--------|-------------------|-------------------|-------------|
| Tool definition tokens | 203 | 186 | 2,044 |
| Avg tool call latency | 2.0 ms | 33.5 ms | 3.0 ms |
| Avg total task time | 11.8 s | 9.6 s | 15.3 s |
| Avg API input tokens | 3,413 | 3,318 | 17,354 |
| Avg API output tokens | 476 | 480 | 646 |

### GPT-4o

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (stdio) |
|--------|-------------------|-------------------|-------------|
| Tool definition tokens | 227 | 210 | 2,156 |
| Avg tool call latency | 1.8 ms | 29.0 ms | 3.0 ms |
| Avg total task time | 6.0 s | 3.5 s | 2.0 s |
| Avg API input tokens | 1,199 | 1,152 | 2,563 |
| Avg API output tokens | 204 | 212 | 83 |

### Cross-LLM Comparison (Direct approach)

| Metric | Claude Sonnet 4 | GPT-4o |
|--------|-----------------|--------|
| Avg total task time | 11.8 s | 6.0 s |
| Avg API input tokens | 3,413 | 1,199 |
| Avg API output tokens | 476 | 204 |

### Analysis

**1. The real MCP cost is token bloat, not protocol latency**

MCP's JSON-RPC overhead is negligible — 3.0ms per call, comparable to direct (2.0ms). The actual cost is that the MCP filesystem server exposes **14 tools**, and all of their schemas are sent to the LLM on every API call, even though we only need 3. This results in:

- **10x more tokens** in tool definitions (2,044 vs 203 for Claude)
- **5x more API input tokens** per task with Claude (17,354 vs 3,413)
- **30% longer end-to-end time** with Claude (15.3s vs 11.8s)

This is a per-turn cost. In a 10-turn agentic conversation, the overhead compounds.

**2. Direct and CLI are nearly identical in token cost**

Both send exactly the 3 tool schemas we defined. The only difference is execution overhead: CLI pays ~30ms per subprocess spawn, but this is invisible in total task time because LLM response time dominates.

**3. GPT-4o is faster but less thorough**

GPT-4o completed tasks in roughly half the time of Claude, using significantly fewer tokens. However, GPT's MCP run (2.0s, 83 output tokens) suggests it may have taken shortcuts — completing the task with fewer tool calls or less detailed output. Claude consistently used all tools and produced thorough summaries.

**4. Both LLMs show the same MCP overhead pattern**

Despite different absolute numbers, the ratio holds: MCP tool definitions are ~10x larger than direct, and API input tokens scale accordingly. The overhead is structural (MCP servers expose everything) rather than model-specific.

### Takeaway

For same-process tools, MCP adds cost without benefit. The protocol itself is fast, but MCP servers expose their full tool surface — and you pay for every token on every turn. Use MCP where it shines (cross-boundary communication, third-party tools, plugin marketplaces) and direct calls where it doesn't (internal tools you control).

## When to Use What

| Approach | Use when... | Avoid when... |
|----------|-------------|---------------|
| **MCP** | Tools cross process/machine boundaries; third-party tool providers; marketplace/plugin scenarios; you need dynamic tool discovery | Tools are local to the agent process and you control them all |
| **Direct** | Tools run in the same process as the agent; you control all tool implementations; latency and token cost matter | You need to expose tools to external consumers or support a plugin model |
| **CLI** | Wrapping existing scripts or binaries; tools need to be independently testable from the terminal; polyglot toolchains | High-frequency tool calls where subprocess overhead adds up |

## Project Structure

```
mcp-vs-direct-benchmark/
├── src/
│   ├── benchmark.py              # Main benchmark entry point
│   ├── __main__.py               # Module runner
│   ├── harness/
│   │   ├── runner.py             # Benchmark runner (drives the agent loop)
│   │   ├── reporter.py           # Results formatting and comparison
│   │   └── token_counter.py      # Token usage tracking
│   └── tools/
│       ├── interface.py           # Common tool interface
│       ├── mcp/
│       │   └── client.py          # MCP client + server lifecycle
│       ├── direct/
│       │   └── tools.py           # Pydantic-based direct tools
│       └── cli/
│           ├── wrapper.py         # Subprocess wrapper for CLI tools
│           ├── list_dir.py        # Standalone list_directory script
│           ├── read_file.py       # Standalone read_file script
│           └── write_file.py      # Standalone write_file script
├── tests/
│   ├── test_mcp_tools.py
│   ├── test_direct_tools.py
│   ├── test_cli_tools.py
│   └── test_harness.py
├── docs/plans/                    # Design docs and implementation plan
├── pyproject.toml
└── .env.example
```

## License

MIT
