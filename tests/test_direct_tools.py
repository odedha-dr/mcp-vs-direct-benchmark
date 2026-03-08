import pytest

from src.tools.direct.tools import DirectToolProvider


@pytest.fixture
def provider():
    return DirectToolProvider()


@pytest.fixture
def tmp_benchmark_dir(tmp_path):
    hello = tmp_path / "hello.txt"
    hello.write_text("Hello, world!")
    return tmp_path


async def test_list_directory(provider, tmp_benchmark_dir):
    result = await provider.execute("list_directory", {"path": str(tmp_benchmark_dir)})
    assert "hello.txt" in result


async def test_read_file(provider, tmp_benchmark_dir):
    result = await provider.execute("read_file", {"path": str(tmp_benchmark_dir / "hello.txt")})
    assert result == "Hello, world!"


async def test_write_file(provider, tmp_benchmark_dir):
    target = tmp_benchmark_dir / "output.txt"
    result = await provider.execute("write_file", {"path": str(target), "content": "written"})
    assert "success" in result.lower()
    assert target.read_text() == "written"


def test_tool_definitions(provider):
    defs = provider.get_tool_definitions()
    assert len(defs) == 3
    names = {d["name"] for d in defs}
    assert names == {"read_file", "write_file", "list_directory"}
    for d in defs:
        assert "input_schema" in d
        assert "description" in d


async def test_execute_unknown_tool(provider):
    with pytest.raises(ValueError, match="Unknown tool"):
        await provider.execute("nonexistent", {})
