from typing import Protocol


class ToolProvider(Protocol):
    """Common interface for all three tool-wiring approaches."""

    async def setup(self) -> None:
        """Initialize the provider (e.g., start MCP server)."""
        ...

    async def teardown(self) -> None:
        """Clean up resources."""
        ...

    def get_tool_definitions(self) -> list[dict]:
        """Return tool definitions in Claude API format."""
        ...

    async def execute(self, name: str, params: dict) -> str:
        """Execute a tool by name, return result as string."""
        ...
