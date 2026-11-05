"""Launch the hosted compiler installed by pip or uv."""

import os
from pathlib import Path
import sys


def main() -> None:
    source = Path(__file__).resolve().parent / "pystachy.py"
    if not os.environ.get("PYSTACHY_CACHE"):
        cache_home = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
        os.environ["PYSTACHY_CACHE"] = str(Path(cache_home) / "pystachy")
    # Keep the .py argv[0] used to identify hosted compiler inputs for caching.
    os.execv(sys.executable, [sys.executable, "-E", "-B", str(source), *sys.argv[1:]])
