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

Benchmark run on 2026-03-09, 2 runs per approach, same filesystem task (list directory, read file, write summary file). All approaches expose the same 3 tools for a fair apples-to-apples comparison.

### Claude (Sonnet 4)

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP |
|--------|-------------------|-------------------|-----|
| Tool definition tokens | 203 | 186 | 461 |
| Avg tool call latency | 1.8 ms | 28.8 ms | 4.6 ms |
| Avg total task time | 10.8 s | 10.3 s | 10.0 s |
| Avg API input tokens | 3,447 | 3,360 | 4,373 |
| Avg API output tokens | 490 | 482 | 495 |
| Avg API turns | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 |

### GPT-4o

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP |
|--------|-------------------|-------------------|-----|
| Tool definition tokens | 227 | 210 | 485 |
| Avg tool call latency | 2.8 ms | 26.9 ms | 3.3 ms |
| Avg total task time | 3.8 s | 3.6 s | 3.6 s |
| Avg API input tokens | 1,206 | 1,164 | 1,877 |
| Avg API output tokens | 204 | 209 | 210 |
| Avg API turns | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 |

### Cross-LLM Comparison (Direct approach)

| Metric | Claude Sonnet 4 | GPT-4o |
|--------|-----------------|--------|
| Avg total task time | 10.8 s | 3.8 s |
| Avg API input tokens | 3,447 | 1,206 |
| Avg API output tokens | 490 | 204 |
| Avg API turns | 4 | 4 |
| Avg tool calls | 3 | 3 |

### Analysis

All runs completed the same task with identical behavior: 4 API turns, 3 tool calls (list, read, write). No errors, no retries.

**1. MCP overhead exists but isn't dramatic**

With the same 3 tools, MCP adds measurable but modest cost:

- **~2x more tool definition tokens** (461 vs 203) — MCP schemas include richer metadata (annotations, readOnlyHint, etc.)
- **~27% more API input tokens** with Claude (4,373 vs 3,447)
- **No meaningful difference in end-to-end time** — within noise for both LLMs

All three approaches (Direct, CLI, MCP) produce the same task behavior and comparable wall-clock times. The integration method doesn't matter much — LLM response latency dominates.

**2. Claude and GPT-4o differ significantly**

This is the more interesting finding. With identical task behavior (same turns, same tool calls), GPT-4o completes in ~3.8s vs Claude's ~10.8s — nearly **3x faster**. The gap shows up across every metric:

- **2.9x more input tokens** with Claude (3,447 vs 1,206) — same 3 tool definitions, same conversation, but Claude's message format is significantly more verbose
- **2.4x more output tokens** (490 vs 204) — Claude generates longer responses for the same task
- **~3x slower end-to-end** — a combination of higher per-turn latency and more tokens to process

Both models complete the task correctly with the same number of steps. The difference is pure efficiency: GPT-4o's message encoding is more compact and its responses are more concise. For tool-heavy agentic workloads where you're paying per-token and per-second, this gap compounds.

### Takeaway

**MCP vs Direct**: MCP adds ~2x tool definition tokens due to richer schemas, but the impact on total cost and latency is modest. Pick your integration approach based on architecture (same-process vs cross-boundary), not performance.

**Claude vs GPT-4o**: The bigger surprise is the cross-LLM gap. GPT-4o uses ~3x fewer input tokens and ~2.4x fewer output tokens for the same task, resulting in ~3x faster completion. For token-heavy agentic workloads, the choice of LLM matters more than the choice of tool integration.

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
