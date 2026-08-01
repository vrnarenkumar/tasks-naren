"""Makes backend/ (config, graph, prompts) and backend/task3 (parts_catalog)
importable from tests/, which sits outside the backend/ tree so tests aren't
mixed in with application code."""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"

for path in (BACKEND, BACKEND / "task3"):
    path = str(path)
    if path not in sys.path:
        sys.path.insert(0, path)
