from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpToolProvider:
    """Tool provider that connects to the MCP filesystem server via stdio."""

    def __init__(self, allowed_dirs: list[str]):
        self._allowed_dirs = allowed_dirs
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[dict] = []

    async def setup(self) -> None:
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", *self._allowed_dirs],
        )
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

        response = await self._session.list_tools()
        self._tools = []
        for tool in response.tools:
            self._tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            })

    async def teardown(self) -> None:
        await self._exit_stack.aclose()

    def get_tool_definitions(self) -> list[dict]:
        return self._tools

    async def execute(self, name: str, params: dict) -> str:
        if self._session is None:
            raise RuntimeError("Provider not set up. Call setup() first.")

        result = await self._session.call_tool(name, arguments=params)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)
