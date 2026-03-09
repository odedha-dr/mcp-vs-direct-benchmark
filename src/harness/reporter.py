from datetime import datetime

PROVIDER_LABELS = {
    "direct": "Direct (Pydantic)",
    "cli": "CLI (subprocess)",
    "mcp": "MCP (stdio)",
    "mcp (3 tools)": "MCP (3 tools)",
    "mcp (all tools)": "MCP (all 14 tools)",
}

METRICS = [
    ("Tool definition tokens", "tool_definition_tokens", ""),
    ("Avg tool call latency", "avg_call_latency_ms", "ms"),
    ("Avg total task time", "avg_total_time_s", "s"),
    ("Avg API input tokens", "avg_api_input_tokens", ""),
    ("  ↳ cached", "avg_cached_input_tokens", ""),
    ("Avg API output tokens", "avg_api_output_tokens", ""),
    ("Avg API turns", "avg_api_turns", ""),
    ("Avg tool calls", "avg_tool_calls", ""),
]


def format_results(results: dict) -> str:
    """Format benchmark results as markdown.

    results is a dict keyed by LLM name, each containing a dict keyed by provider name.
    Example: {"claude": {"direct": {...}, "cli": {...}, "mcp": {...}}, "gpt": {...}}

    Also supports legacy flat format: {"direct": {...}, "cli": {...}, "mcp": {...}}
    """
    # Detect legacy flat format (no nested LLM keys)
    first_val = next(iter(results.values()))
    if "tool_definition_tokens" in first_val:
        return _format_single_llm(results, None)

    sections = []
    sections.append(f"# Benchmark Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for llm_name, provider_results in results.items():
        sections.append("")
        sections.append(f"## {llm_name}")
        sections.append("")
        sections.append(_format_table(provider_results))

    # Cross-LLM comparison if multiple
    if len(results) > 1:
        sections.append("")
        sections.append("## Cross-LLM Comparison")
        sections.append("")
        sections.append(_format_cross_comparison(results))

    return "\n".join(sections)


def _format_single_llm(provider_results: dict, llm_name: str | None) -> str:
    """Format results for a single LLM (legacy format)."""
    lines = [f"# Benchmark Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    if llm_name:
        lines.append(f"\n## {llm_name}")
    lines.append("")
    lines.append(_format_table(provider_results))

    if "direct" in provider_results and "mcp" in provider_results:
        lines.extend(_format_takeaways(provider_results))

    return "\n".join(lines)


def _format_table(provider_results: dict) -> str:
    """Format a comparison table for provider results."""
    providers = list(provider_results.keys())
    labels = [PROVIDER_LABELS.get(p, p) for p in providers]

    header = "| Metric | " + " | ".join(labels) + " |"
    separator = "|--------" + "".join("|-" + "-" * max(len(l), 5) for l in labels) + "|"

    lines = [header, separator]

    for label, key, unit in METRICS:
        suffix = f" {unit}" if unit else ""
        values = [f"{provider_results[p][key]:.1f}{suffix}" for p in providers]
        lines.append(f"| {label} | " + " | ".join(values) + " |")

    return "\n".join(lines)


def _format_takeaways(provider_results: dict) -> list[str]:
    """Generate takeaway lines from results."""
    direct = provider_results.get("direct", {})
    mcp = provider_results.get("mcp", {})
    if not direct or not mcp:
        return []

    return [
        "",
        "### Key Takeaways",
        "",
        f"- **Token overhead**: MCP adds ~{mcp['tool_definition_tokens'] - direct['tool_definition_tokens']:.0f} extra tokens in tool definitions",
        f"- **Latency**: Direct is {mcp['avg_call_latency_ms'] / max(direct['avg_call_latency_ms'], 0.01):.0f}x faster than MCP per tool call",
        f"- **End-to-end**: Direct completes tasks in {direct['avg_total_time_s']:.1f}s vs MCP's {mcp['avg_total_time_s']:.1f}s",
    ]


def _format_cross_comparison(results: dict) -> str:
    """Compare the same provider across different LLMs."""
    lines = []

    # Compare "direct" across LLMs as the baseline
    lines.append("| Metric | " + " | ".join(results.keys()) + " |")
    lines.append("|--------" + "|---------" * len(results) + "|")

    for label, key, unit in METRICS:
        suffix = f" {unit}" if unit else ""
        values = []
        for llm_name, provider_results in results.items():
            # Use "direct" as representative for cross-LLM comparison
            if "direct" in provider_results:
                values.append(f"{provider_results['direct'][key]:.1f}{suffix}")
            else:
                first_provider = next(iter(provider_results.values()))
                values.append(f"{first_provider[key]:.1f}{suffix}")
        lines.append(f"| {label} (direct) | " + " | ".join(values) + " |")

    return "\n".join(lines)
