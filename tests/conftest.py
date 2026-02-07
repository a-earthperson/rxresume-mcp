from __future__ import annotations

import sys
from pathlib import Path


def _ensure_local_src_on_path() -> None:
    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir.parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_ensure_local_src_on_path()
