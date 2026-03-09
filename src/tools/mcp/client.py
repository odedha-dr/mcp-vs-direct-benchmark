from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# The 3 tools we benchmark — matches direct/CLI tool surface
FILTERED_TOOLS = {"read_text_file", "write_file", "list_directory"}


class McpToolProvider:
    """Tool provider that connects to the MCP filesystem server via stdio.

    Args:
        allowed_dirs: Directories the MCP server can access.
        filter_tools: If True (default), only expose the 3 tools that match
            the direct/CLI providers for a fair comparison. If False, expose
            all tools from the MCP server (shows real-world overhead).
    """

    def __init__(self, allowed_dirs: list[str], filter_tools: bool = True):
        self._allowed_dirs = allowed_dirs
        self._filter_tools = filter_tools
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
            if self._filter_tools and tool.name not in FILTERED_TOOLS:
                continue
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
