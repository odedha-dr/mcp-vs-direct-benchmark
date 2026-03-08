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
