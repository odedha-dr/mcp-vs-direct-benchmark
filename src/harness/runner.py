import json
import time

import anthropic
import openai

from src.harness.token_counter import estimate_tokens


def _to_openai_tools(tool_defs: list[dict]) -> list[dict]:
    """Convert Claude-format tool definitions to OpenAI format."""
    result = []
    for tool in tool_defs:
        schema = dict(tool.get("input_schema", {}))
        schema.pop("title", None)
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": schema,
            },
        })
    return result


async def _run_anthropic(client, model, tool_defs, prompt, all_call_latencies, provider):
    """Run one Anthropic agentic loop."""
    messages = [{"role": "user", "content": prompt}]
    total_input = 0
    total_output = 0
    tool_calls_log = []
    api_turns = 0
    final_response = ""
    start_time = time.perf_counter()

    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            tools=tool_defs,
            messages=messages,
        )
        api_turns += 1

        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            # Extract final text response
            for block in response.content:
                if hasattr(block, "text"):
                    final_response += block.text
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                call_start = time.perf_counter()
                result = await provider.execute(block.name, block.input)
                call_end = time.perf_counter()
                latency = (call_end - call_start) * 1000
                all_call_latencies.append(latency)

                tool_calls_log.append({
                    "tool": block.name,
                    "input": block.input,
                    "result_preview": result[:200],
                    "latency_ms": round(latency, 1),
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    total_time = time.perf_counter() - start_time

    trace = {
        "api_turns": api_turns,
        "tool_calls": tool_calls_log,
        "total_tool_calls": len(tool_calls_log),
        "final_response_preview": final_response[:500],
        "final_response_length": len(final_response),
    }

    return total_input, total_output, total_time, trace


async def _run_openai(client, model, tool_defs, prompt, all_call_latencies, provider):
    """Run one OpenAI agentic loop."""
    openai_tools = _to_openai_tools(tool_defs)
    messages = [{"role": "user", "content": prompt}]
    total_input = 0
    total_output = 0
    tool_calls_log = []
    api_turns = 0
    final_response = ""
    start_time = time.perf_counter()

    while True:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            tools=openai_tools,
            messages=messages,
        )
        api_turns += 1

        choice = response.choices[0]
        total_input += response.usage.prompt_tokens
        total_output += response.usage.completion_tokens

        if choice.finish_reason != "tool_calls":
            if choice.message.content:
                final_response = choice.message.content
            break

        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            call_start = time.perf_counter()
            params = json.loads(tool_call.function.arguments)
            result = await provider.execute(tool_call.function.name, params)
            call_end = time.perf_counter()
            latency = (call_end - call_start) * 1000
            all_call_latencies.append(latency)

            tool_calls_log.append({
                "tool": tool_call.function.name,
                "input": params,
                "result_preview": result[:200],
                "latency_ms": round(latency, 1),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    total_time = time.perf_counter() - start_time

    trace = {
        "api_turns": api_turns,
        "tool_calls": tool_calls_log,
        "total_tool_calls": len(tool_calls_log),
        "final_response_preview": final_response[:500],
        "final_response_length": len(final_response),
    }

    return total_input, total_output, total_time, trace


async def run_benchmark(
    provider,
    prompt: str,
    model: str,
    llm: str = "anthropic",
    runs: int = 3,
) -> dict:
    """Run a benchmark with the specified LLM provider."""
    tool_defs = provider.get_tool_definitions()
    tool_def_tokens = estimate_tokens(
        _to_openai_tools(tool_defs) if llm == "openai" else tool_defs
    )

    if llm == "anthropic":
        client = anthropic.AsyncAnthropic()
        run_fn = _run_anthropic
    else:
        client = openai.AsyncOpenAI()
        run_fn = _run_openai

    all_call_latencies = []
    all_total_times = []
    all_input_tokens = []
    all_output_tokens = []
    all_traces = []

    for _ in range(runs):
        total_input, total_output, total_time, trace = await run_fn(
            client, model, tool_defs, prompt, all_call_latencies, provider
        )
        all_total_times.append(total_time)
        all_input_tokens.append(total_input)
        all_output_tokens.append(total_output)
        all_traces.append(trace)

    return {
        "tool_definition_tokens": tool_def_tokens,
        "avg_call_latency_ms": sum(all_call_latencies) / max(len(all_call_latencies), 1),
        "avg_total_time_s": sum(all_total_times) / len(all_total_times),
        "avg_api_input_tokens": sum(all_input_tokens) / len(all_input_tokens),
        "avg_api_output_tokens": sum(all_output_tokens) / len(all_output_tokens),
        "avg_api_turns": sum(t["api_turns"] for t in all_traces) / len(all_traces),
        "avg_tool_calls": sum(t["total_tool_calls"] for t in all_traces) / len(all_traces),
        "traces": all_traces,
    }
