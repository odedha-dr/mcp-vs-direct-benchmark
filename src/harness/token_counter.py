import json


def estimate_tokens(data: str | dict | list) -> int:
    """Estimate token count using ~4 chars per token heuristic.

    For precise counts, use anthropic.count_tokens() — but this avoids
    an API call and is accurate enough for comparison purposes.
    """
    if isinstance(data, (dict, list)):
        text = json.dumps(data)
    else:
        text = data
    return len(text) // 4
