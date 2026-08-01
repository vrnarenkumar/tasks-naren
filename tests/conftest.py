"""Makes backend/ (config, graph, prompts) and tasks/task3 (parts_catalog)
importable from tests/, which sits outside those trees so tests aren't
mixed in with application code."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for path in (ROOT / "backend", ROOT / "tasks" / "task3"):
    path = str(path)
    if path not in sys.path:
        sys.path.insert(0, path)
