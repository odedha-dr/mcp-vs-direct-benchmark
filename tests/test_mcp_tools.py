import shutil

import pytest

from src.tools.mcp.client import McpToolProvider

# Skip all tests in this module if npx is not available
pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None,
    reason="npx not available — required for MCP filesystem server",
)


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    hello = tmp_path / "hello.txt"
    hello.write_text("Hello, world!")
    return tmp_path


@pytest.fixture
async def provider(tmp_benchmark_dir):
    p = McpToolProvider(allowed_dirs=[str(tmp_benchmark_dir)])
    await p.setup()
    yield p
    try:
        await p.teardown()
    except RuntimeError:
        # The MCP stdio_client uses anyio task groups that may raise
        # when teardown runs in a different task context than setup.
        # This is a known limitation with pytest-asyncio fixtures.
        pass


async def test_tool_definitions(provider):
    defs = provider.get_tool_definitions()
    names = {d["name"] for d in defs}
    # MCP filesystem server exposes these among others
    assert "list_directory" in names
    assert "write_file" in names
    # It uses "read_text_file" not "read_file"
    assert "read_text_file" in names


async def test_list_directory(provider, tmp_benchmark_dir):
    result = await provider.execute("list_directory", {"path": str(tmp_benchmark_dir)})
    assert "hello.txt" in result


async def test_read_file(provider, tmp_benchmark_dir):
    result = await provider.execute(
        "read_text_file", {"path": str(tmp_benchmark_dir / "hello.txt")}
    )
    assert "Hello, world!" in result


async def test_write_file(provider, tmp_benchmark_dir):
    target = tmp_benchmark_dir / "output.txt"
    await provider.execute("write_file", {"path": str(target), "content": "written"})
    assert target.read_text() == "written"
