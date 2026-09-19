"""PostToolUse hook: format the Python file that was just edited. Formatting only, no auto-fixes."""

import json
import subprocess
import sys

path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
if path.endswith(".py"):
    subprocess.run(["uv", "run", "ruff", "format", "--quiet", path], check=False)
