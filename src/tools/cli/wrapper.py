import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

TOOLS = {
    "read_file": {
        "script": "read_file.py",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file to read"}},
            "required": ["path"],
        },
    },
    "write_file": {
        "script": "write_file.py",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
    },
    "list_directory": {
        "script": "list_dir.py",
        "description": "List the contents of a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the directory to list"},
            },
            "required": ["path"],
        },
    },
}


class CliToolProvider:
    """Tool provider that executes standalone Python scripts via subprocess."""

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": config["description"],
                "input_schema": config["input_schema"],
            }
            for name, config in TOOLS.items()
        ]

    async def execute(self, name: str, params: dict) -> str:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")

        script = SCRIPT_DIR / TOOLS[name]["script"]
        cmd = [sys.executable, str(script)]
        for key, value in params.items():
            cmd.extend([f"--{key}", str(value)])

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return f"Error: {stderr.decode()}"
        return stdout.decode()
