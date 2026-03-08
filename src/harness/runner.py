import time
import anthropic
from src.harness.token_counter import estimate_tokens


async def run_benchmark(
    provider,
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    runs: int = 3,
) -> dict:
    """Run a benchmark: send prompt to Claude with the provider's tools, measure everything."""
    client = anthropic.AsyncAnthropic()
    tool_defs = provider.get_tool_definitions()
    tool_def_tokens = estimate_tokens(tool_defs)

    all_call_latencies = []
    all_total_times = []
    all_input_tokens = []
    all_output_tokens = []

    for _ in range(runs):
        messages = [{"role": "user", "content": prompt}]
        total_input = 0
        total_output = 0
        start_time = time.perf_counter()

        while True:
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                tools=tool_defs,
                messages=messages,
            )

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                break

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    call_start = time.perf_counter()
                    result = await provider.execute(block.name, block.input)
                    call_end = time.perf_counter()
                    all_call_latencies.append((call_end - call_start) * 1000)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        total_time = time.perf_counter() - start_time
        all_total_times.append(total_time)
        all_input_tokens.append(total_input)
        all_output_tokens.append(total_output)

    return {
        "tool_definition_tokens": tool_def_tokens,
        "avg_call_latency_ms": sum(all_call_latencies) / max(len(all_call_latencies), 1),
        "avg_total_time_s": sum(all_total_times) / len(all_total_times),
        "avg_api_input_tokens": sum(all_input_tokens) / len(all_input_tokens),
        "avg_api_output_tokens": sum(all_output_tokens) / len(all_output_tokens),
    }
