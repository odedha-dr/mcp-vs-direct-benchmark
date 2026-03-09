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
- Anthropic API key

### Setup

```bash
git clone https://github.com/odedha/mcp-vs-direct-benchmark.git
cd mcp-vs-direct-benchmark

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

uv sync
```

### Run

```bash
uv run python -m src.benchmark
```

Results are printed to the terminal as a comparison table.

## Results

Benchmark run on 2026-03-09, 2 runs per approach, Claude Sonnet, same filesystem task (list directory, read file, write file).

### Raw Numbers

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (stdio) |
|--------|-------------------|-------------------|-------------|
| Tool definition tokens | 203 | 186 | 2,044 |
| Avg tool call latency | 2.3 ms | 77.7 ms | 2.7 ms |
| Avg total task time | 10.1 s | 10.3 s | 16.1 s |
| Avg API input tokens | 3,439 | 3,345 | 17,426 |
| Avg API output tokens | 475 | 479 | 653 |

### Analysis

**The overhead isn't where most people expect.**

MCP's JSON-RPC protocol latency is negligible (2.7ms per call — comparable to direct). The real cost is **token bloat**. The MCP filesystem server exposes 14 tools, and all of their schemas are sent to the LLM on every turn — even though we only need 3. This results in:

- **10x more tokens** in tool definitions (2,044 vs 203)
- **5x more API input tokens** per task (17,426 vs 3,439)
- **60% longer end-to-end time** (16.1s vs 10.1s) — the extra time is Claude processing larger prompts, not protocol overhead

Direct and CLI have nearly identical token costs because they send exactly the same 3 tool schemas. CLI's per-call latency is higher (77.7ms vs 2.3ms) due to subprocess spawning, but this is invisible in total task time because LLM response time dominates.

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
