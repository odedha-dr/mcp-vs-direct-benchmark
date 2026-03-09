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

Benchmark run on 2026-03-09, 2 runs per approach, same filesystem task (list directory, read file, write summary file). MCP is tested two ways: filtered to the same 3 tools (fair apples-to-apples) and unfiltered with all 14 tools (real-world MCP usage).

### Claude (Sonnet 4)

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (3 tools) | MCP (all 14 tools) |
|--------|-------------------|-------------------|---------------|---------------------|
| Tool definition tokens | 203 | 186 | 461 | 2,044 |
| Avg tool call latency | 1.0 ms | 28.6 ms | 3.1 ms | 2.9 ms |
| Avg total task time | 9.8 s | 10.1 s | 12.0 s | 15.9 s |
| Avg API input tokens | 3,423 | 3,332 | 6,061 | 17,427 |
| Avg API output tokens | 464 | 477 | 590 | 667 |

### GPT-4o

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (3 tools) | MCP (all 14 tools) |
|--------|-------------------|-------------------|---------------|---------------------|
| Tool definition tokens | 227 | 210 | 485 | 2,156 |
| Avg tool call latency | 2.7 ms | 29.3 ms | 3.0 ms | 1.9 ms |
| Avg total task time | 3.9 s | 3.4 s | 3.2 s | 2.8 s |
| Avg API input tokens | 1,209 | 1,159 | 1,810 | 2,645 |
| Avg API output tokens | 217 | 208 | 188 | 155 |

### Cross-LLM Comparison (Direct approach)

| Metric | Claude Sonnet 4 | GPT-4o |
|--------|-----------------|--------|
| Avg total task time | 9.8 s | 3.9 s |
| Avg API input tokens | 3,423 | 1,209 |
| Avg API output tokens | 464 | 217 |

### Analysis

**1. MCP protocol overhead is real but modest (fair comparison)**

With the same 3 tools, MCP still costs more than direct:

- **2.3x more tool definition tokens** (461 vs 203) — MCP schemas include richer metadata (annotations, readOnlyHint, etc.)
- **1.8x more API input tokens** with Claude (6,061 vs 3,423)
- **22% longer end-to-end time** with Claude (12.0s vs 9.8s)

This is the pure protocol overhead — same tools, different wiring.

**2. Unfiltered MCP is where the real cost hides**

In practice, MCP servers expose their full tool surface. The filesystem server sends 14 tools when you only need 3. This balloons the cost:

- **10x more tool definition tokens** (2,044 vs 203)
- **5x more API input tokens** with Claude (17,427 vs 3,423)
- **62% longer end-to-end time** with Claude (15.9s vs 9.8s)

This is the typical real-world penalty — and it compounds on every turn.

**3. Direct and CLI are equivalent in token cost**

Both send exactly the 3 tool schemas we defined. CLI pays ~29ms per subprocess spawn, but this is invisible in total task time because LLM response time dominates.

**4. GPT-4o is faster but less thorough**

GPT-4o completed tasks in roughly half the time of Claude, using significantly fewer tokens. However, GPT's low output token counts (155-217 vs Claude's 464-667) suggest it takes shortcuts — fewer tool calls or less detailed output. Claude consistently used all tools and produced thorough summaries.

**5. Both LLMs confirm the same overhead pattern**

Despite different absolute numbers, the ratios are consistent: MCP schemas are larger, API input tokens scale with tool count, and the overhead is structural rather than model-specific.

### Takeaway

MCP has two distinct costs:

1. **Protocol overhead** (~2x token cost even with matched tools) — MCP schemas carry richer metadata than hand-crafted Pydantic schemas.
2. **Tool surface bloat** (~10x token cost in practice) — MCP servers expose everything, and you pay for every tool definition on every turn.

For same-process tools you control, direct Pydantic calls are cheaper and faster. Use MCP where it adds value: cross-boundary communication, third-party tool providers, and plugin marketplaces.

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
