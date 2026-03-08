# MCP vs Direct vs CLI Benchmark — Design

**Author:** Oded Har-Tal
**Date:** 2026-03-08
**Status:** Approved

---

## 1. Purpose

Compare three approaches to wiring tools in an AI agent, using filesystem operations as the benchmark:

1. **MCP** — JSON-RPC over stdio, using the official MCP filesystem server
2. **Direct API** — Pydantic in-process functions, wired to Claude's `tools` parameter
3. **CLI** — Subprocess calls to standalone Python scripts

Measure token overhead, invocation latency, and end-to-end task time.

## 2. Project Structure

```
src/
├── tools/
│   ├── interface.py      # ToolProvider Protocol
│   ├── mcp/
│   │   ├── server.py     # MCP filesystem server config
│   │   └── client.py     # MCP client wrapper
│   ├── direct/
│   │   └── tools.py      # Pydantic in-process tools
│   └── cli/
│       ├── read_file.py  # Standalone CLI script
│       ├── write_file.py
│       ├── list_dir.py
│       └── wrapper.py    # Subprocess wrapper implementing ToolProvider
├── harness/
│   ├── runner.py         # Runs prompt through Claude with a ToolProvider
│   ├── token_counter.py  # Counts tokens in tool definitions
│   └── reporter.py       # Formats results as markdown table
└── benchmark.py          # Entry point
```

## 3. Common Interface

```python
class ToolProvider(Protocol):
    async def get_tool_definitions(self) -> list[dict]: ...
    async def execute(self, name: str, params: dict) -> str: ...
    async def setup(self) -> None: ...
    async def teardown(self) -> None: ...
```

## 4. Three Tools

| Tool | Input | Operation |
|------|-------|-----------|
| read_file | path: str | Read file contents |
| write_file | path: str, content: str | Write content to file |
| list_directory | path: str | List directory contents |

## 5. Measurements

- **Tool definition tokens**: size of `tools` parameter per approach
- **Per-call latency**: wall-clock time for tool execution (excludes LLM time)
- **Total wall-clock time**: prompt to final response
- **Total API tokens**: input + output from `usage` field

## 6. Benchmark Prompt

> "List the files in /tmp/benchmark, read the file called hello.txt, then write a file called summary.txt with what you found."

Run 3 times per approach, report averages.

## 7. Tech Stack

- Python 3.12+, UV
- anthropic, pydantic, mcp, rich, typer
- Node.js (for MCP filesystem server)

## 8. Deliverable

README with: the question, three approaches explained, methodology, results table, practical guidance, "run it yourself" instructions.
