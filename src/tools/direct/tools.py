import os

from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    path: str = Field(description="Path to the file to read")


class WriteFileInput(BaseModel):
    path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class ListDirectoryInput(BaseModel):
    path: str = Field(description="Path to the directory to list")


TOOLS = {
    "read_file": {
        "model": ReadFileInput,
        "description": "Read the contents of a file",
    },
    "write_file": {
        "model": WriteFileInput,
        "description": "Write content to a file",
    },
    "list_directory": {
        "model": ListDirectoryInput,
        "description": "List the contents of a directory",
    },
}


class DirectToolProvider:
    """In-process Pydantic tool provider. Zero serialization overhead."""

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass

    def get_tool_definitions(self) -> list[dict]:
        result = []
        for name, config in TOOLS.items():
            schema = config["model"].model_json_schema()
            schema.pop("title", None)
            result.append({
                "name": name,
                "description": config["description"],
                "input_schema": schema,
            })
        return result

    async def execute(self, name: str, params: dict) -> str:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")

        validated = TOOLS[name]["model"](**params)

        if name == "read_file":
            return _read_file(validated.path)
        elif name == "write_file":
            return _write_file(validated.path, validated.content)
        elif name == "list_directory":
            return _list_directory(validated.path)

        raise ValueError(f"Unknown tool: {name}")


def _read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


def _write_file(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


def _list_directory(path: str) -> str:
    entries = os.listdir(path)
    return "\n".join(entries)
