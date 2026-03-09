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
| Avg tool call latency | 1.7 ms | 30.7 ms | 4.4 ms | 4.7 ms |
| Avg total task time | 11.5 s | 10.5 s | 10.2 s | 11.2 s |
| Avg API input tokens | 3,458 | 3,366 | 4,373 | 1,805 |
| Avg API output tokens | 485 | 502 | 481 | 491 |
| Avg API turns | 4 | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 | 3 |
| Cache creation tokens | 0 | 0 | 0 | 1,135 |
| Cache read tokens | 0 | 0 | 0 | 7,945 |

Prompt caching is enabled (via `cache_control` on tool definitions). Direct, CLI, and MCP (3 tools) show zero caching because their tool definitions fall below Anthropic's 1,024-token minimum for cacheable prefixes. MCP (all 14 tools) at 2,044 tokens qualifies — the 2,270-token tool prefix is cached on turn 1 and read from cache on all subsequent turns, reducing `input_tokens` from ~2,489/turn to ~450/turn.

### GPT-4o

| Metric | Direct (Pydantic) | CLI (subprocess) | MCP (3 tools) | MCP (all 14 tools) |
|--------|-------------------|-------------------|---------------|---------------------|
| Tool definition tokens | 227 | 210 | 485 | 2,156 |
| Avg tool call latency | 2.9 ms | 28.8 ms | 3.4 ms | 4.0 ms |
| Avg total task time | 3.8 s | 4.4 s | 4.1 s | 4.2 s |
| Avg API input tokens | 1,231 | 1,186 | 1,903 | 5,349 |
| Avg API output tokens | 201 | 211 | 226 | 214 |
| Avg API turns | 4 | 4 | 4 | 4 |
| Avg tool calls | 3 | 3 | 3 | 3 |
| Cached tokens | 0 | 0 | 0 | 3,840 |

OpenAI caches automatically (no opt-in needed). Similar to Claude, only MCP (all 14 tools) has a large enough prefix to trigger caching — ~1,150-1,400 tokens cached per turn starting from turn 2.

### Cross-LLM Comparison (Direct approach)

| Metric | Claude Sonnet 4 | GPT-4o |
|--------|-----------------|--------|
| Avg total task time | 11.5 s | 3.8 s |
| Avg API input tokens | 3,458 | 1,231 |
| Avg API output tokens | 485 | 201 |
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

**5. Prompt caching dramatically reduces the cost of large tool sets**

Both providers support prompt caching, but with different mechanisms:

**Anthropic (Claude)** — requires explicit `cache_control` breakpoints on tool definitions:

| Turn | input_tokens | cache_creation | cache_read | Notes |
|------|-------------|----------------|------------|-------|
| 1 (Run 1) | 218 | 2,270 | 0 | Tool defs written to cache |
| 2 | 370 | 0 | 2,270 | Tool defs read from cache |
| 3 | 503 | 0 | 2,270 | Tool defs read from cache |
| 4 | 718 | 0 | 2,270 | Tool defs read from cache |
| 1 (Run 2) | 218 | 0 | 2,270 | Cache persists across runs |

With caching enabled, MCP (all 14 tools) `input_tokens` drops from ~2,489/turn (uncached) to ~450/turn — the 2,270-token tool prefix is paid once and read from cache on every subsequent turn. Cache read tokens are billed at 10% of the normal input token rate, so the effective cost reduction is ~90% on the tool definition portion.

**OpenAI (GPT-4o)** — caches automatically, no opt-in needed:

The "MCP (all tools)" variant shows ~1,150-1,400 cached tokens per turn starting from turn 2. Automatic caching is convenient but less aggressive than Anthropic's explicit approach — the cached prefix is smaller and doesn't persist as reliably across runs.

**Key insight**: Both providers only cache when the tool definition prefix exceeds a minimum threshold (~1,024 tokens). Direct (203 tokens), CLI (186 tokens), and MCP with 3 tools (461 tokens) are all too small to trigger caching with either provider. This means caching is most valuable exactly where it's most needed — large MCP tool surfaces.

### Takeaway

MCP has two distinct costs:

1. **Protocol overhead** (~2x tool definition tokens with matched tools) — MCP schemas carry richer metadata. Impact on total cost is modest for short tasks.
2. **Tool surface bloat** (~10x tool definition tokens in practice) — MCP servers expose everything, and you pay for every tool on every turn. This is where the real cost hides, especially in longer conversations.

Prompt caching significantly mitigates the tool surface bloat:

3. **Prompt caching** (90% cost reduction on cached tool definitions) — With caching enabled, the 2,044-token MCP tool prefix is paid once and read from cache at 10% cost on subsequent turns. Anthropic requires explicit `cache_control` breakpoints; OpenAI caches automatically. Either way, caching only activates above ~1,024 tokens, so it helps exactly where it's needed most — large MCP tool surfaces.

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
