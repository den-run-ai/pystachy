"""Keep research branches' scratch artifacts out of the production Git index."""

import os
from pathlib import Path
import subprocess
import sys


def check(root: Path) -> int:
    """Check tracked/staged paths, including ignored files already in the index."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--full-name", "-z"],
            cwd=root, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"repository hygiene: cannot read Git index: {error}", file=sys.stderr)
        return 2
    forbidden = sorted({os.fsdecode(path) for path in result.stdout.split(b"\0")
                        if path == b"research" or path.startswith(b"research/")})
    if forbidden:
        print("repository hygiene: research artifacts belong on a separate research branch; "
              "promote maintained tests/tools separately:", file=sys.stderr)
        for path in forbidden:
            print(f"  {path!r}", file=sys.stderr)
        return 1
    print("repository hygiene: no tracked research artifacts")
    return 0


if __name__ == "__main__":
    sys.exit(check(Path(__file__).resolve().parent.parent))
