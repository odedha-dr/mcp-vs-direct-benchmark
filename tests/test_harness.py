from src.harness.token_counter import estimate_tokens
from src.harness.reporter import format_results


def test_estimate_tokens():
    text = "Hello, world! This is a test."
    count = estimate_tokens(text)
    assert 5 < count < 20


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
    assert "direct" in md.lower() or "Direct" in md
    assert "mcp" in md.lower() or "MCP" in md
    assert "cli" in md.lower() or "CLI" in md
    assert "|" in md
