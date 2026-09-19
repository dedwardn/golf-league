"""Structure guard: one home per concept, and no oversized files.

Fails when:
- a source file exceeds MAX_LINES, or
- the same public top-level function or class name is defined in two modules.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "league"
MAX_LINES = 300


def public_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return [n.name for n in tree.body if isinstance(n, kinds) and not n.name.startswith("_")]


def main() -> int:
    problems: list[str] = []
    homes: dict[str, list[str]] = defaultdict(list)

    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(SRC.parent))
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LINES:
            problems.append(f"{rel}: {lines} lines, limit is {MAX_LINES}. Split by concept.")
        for name in public_names(path):
            homes[name].append(rel)

    for name, files in sorted(homes.items()):
        if len(files) > 1:
            problems.append(f"'{name}' is defined in {len(files)} modules: {', '.join(files)}")

    for problem in problems:
        sys.stderr.write(problem + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
