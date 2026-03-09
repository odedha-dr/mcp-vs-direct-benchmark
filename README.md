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
| **Cache behavior** | How each provider's caching reduces repeated token costs |

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
| Avg tool call latency | 3.4 ms | 31.9 ms | 4.5 ms | 3.7 ms |
| Avg total task time | 9.8 s | 10.0 s | 9.2 s | 10.3 s |
| Avg API input tokens | 3,463 | 3,373 | 4,379 | 10,898 |
| Avg API output tokens | 482 | 489 | 497 | 493 |
| Avg API turns | 4 | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 | 3 |
| Cache creation tokens | 0 | 0 | 0 | 0 |
| Cache read tokens | 0 | 0 | 0 | 0 |

### GPT-4o

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (3 tools) | MCP (all 14 tools) |
|--------|-------------------|-------------------|---------------|---------------------|
| Tool definition tokens | 227 | 210 | 485 | 2,156 |
| Avg tool call latency | 2.4 ms | 31.3 ms | 3.3 ms | 3.3 ms |
| Avg total task time | 4.8 s | 4.0 s | 3.4 s | 4.4 s |
| Avg API input tokens | 1,245 | 1,193 | 1,910 | 5,356 |
| Avg API output tokens | 245 | 218 | 228 | 217 |
| Avg API turns | 4 | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 | 3 |
| Cached tokens | 0 | 0 | 0 | 3,136 |

### Cross-LLM Comparison (Direct approach)

| Metric | Claude Sonnet 4 | GPT-4o |
|--------|-----------------|--------|
| Avg total task time | 9.8 s | 4.8 s |
| Avg API input tokens | 3,463 | 1,245 |
| Avg API output tokens | 482 | 245 |
| Avg API turns | 4 | 4 |
| Avg tool calls | 3 | 3 |

### Analysis

All runs completed the same task with the same behavior: 4 API turns, 3 tool calls (list, read, write). No errors, no retries. This isolates pure overhead differences.

**1. MCP protocol overhead is modest with matched tools**

With the same 3 tools, MCP adds some cost but not dramatic:

- **2.3x more tool definition tokens** (461 vs 203) — MCP schemas include richer metadata (annotations, readOnlyHint, etc.)
- **27% more API input tokens** with Claude (4,405 vs 3,479)
- **No meaningful difference in end-to-end time** (10.3s vs 11.3s) — within noise

The protocol overhead exists but is small when tool counts are matched.

**2. Unfiltered MCP is where the real cost hides**

In practice, MCP servers expose their full tool surface. The filesystem server sends 14 tools when you only need 3:

- **10x more tool definition tokens** (2,044 vs 203)
- **3.1x more API input tokens** with Claude (10,930 vs 3,479)
- **4.3x more API input tokens** with GPT (5,349 vs 1,232)

End-to-end time stays comparable because tool definitions are a fixed cost per turn, and with only 4 turns the absolute overhead is small. In longer agentic conversations (10-20 turns), this compounds significantly.

**3. Direct and CLI are equivalent**

Both send the same 3 tool schemas and produce identical behavior (4 turns, 3 calls). CLI pays ~30ms per subprocess spawn, but this is invisible in total task time because LLM response time dominates.

**4. GPT-4o is ~2x faster than Claude per task**

With identical task behavior (same turns, same tool calls), GPT-4o consistently completes in ~4.8s vs Claude's ~9.8s. The difference comes from:

- **Lower per-turn latency** — GPT responds faster per API call
- **More concise output** — 245 vs 482 output tokens (half the verbosity)
- **Fewer input tokens** — 1,245 vs 3,463 (GPT's message format is more compact)

Both complete the task correctly with the same number of steps.

**5. Caching behavior differs fundamentally between providers**

The benchmark tracks prompt caching to understand the true cost of repeated tool definitions across turns:

- **Anthropic (Claude)**: Reports zero cache hits across all runs. Anthropic's prompt caching requires explicit `cache_control` breakpoints in the request — it does not cache automatically. Without opting in, every turn pays the full cost of tool definitions. This means the 2,044-token tool definition overhead in "MCP (all tools)" is paid in full on every single API turn.

- **OpenAI (GPT-4o)**: Automatic server-side caching kicks in, but only where the prefix is large enough. The "MCP (all tools)" variant (2,156 tool definition tokens) shows ~1,150-1,400 cached tokens on turns 2-4, meaning the static tool definition prefix gets cached within a conversation. Smaller tool sets (direct, CLI, MCP 3 tools) show zero caching — the prefix is too small to trigger OpenAI's automatic cache.

**Implications**: For agents with many tools or long conversations, OpenAI's automatic caching partially offsets the MCP tool surface bloat. With Anthropic, you must explicitly opt into caching to get this benefit — otherwise tool definition tokens compound linearly with every turn.

### Takeaway

MCP has two distinct costs:

1. **Protocol overhead** (~2x tool definition tokens with matched tools) — MCP schemas carry richer metadata. Impact on total cost is modest for short tasks.
2. **Tool surface bloat** (~10x tool definition tokens in practice) — MCP servers expose everything, and you pay for every tool on every turn. This is where the real cost hides, especially in longer conversations.

Caching can mitigate the tool surface bloat, but the mechanism differs:

- **OpenAI** caches automatically when the prompt prefix is large enough (~1,024+ tokens). This means "MCP (all tools)" gets partial caching for free, reducing the per-turn cost of repeated tool definitions.
- **Anthropic** requires explicit `cache_control` breakpoints. Without them, you pay full price on every turn. If you use MCP with many tools on Anthropic, enabling prompt caching on the tool definitions is critical to controlling cost.

For same-process tools you control, direct Pydantic calls are leaner. Use MCP where it adds value: cross-boundary communication, third-party tool providers, and plugin marketplaces.

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
