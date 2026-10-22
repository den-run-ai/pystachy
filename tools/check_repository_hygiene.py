"""Keep research artifacts and special-character paths out of the Git index."""

import os
from pathlib import Path
import re
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
    paths = {path for path in result.stdout.split(b"\0") if path}
    forbidden = sorted({os.fsdecode(path) for path in paths
                        if path == b"research" or path.startswith(b"research/")})
    unusual = sorted(os.fsdecode(path) for path in paths
                     if not re.fullmatch(rb"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path))
    if forbidden:
        print("repository hygiene: research artifacts belong on a separate research branch; "
              "promote maintained tests/tools separately:", file=sys.stderr)
        for path in forbidden:
            print(f"  {path!r}", file=sys.stderr)
    if unusual:
        print("repository hygiene: tracked path components may contain only "
              "ASCII letters, digits, '.', '_' and '-'; generate special-character "
              "test paths in temporary directories:", file=sys.stderr)
        for path in unusual:
            print(f"  {path!r}", file=sys.stderr)
    if forbidden or unusual:
        return 1
    print("repository hygiene: tracked paths are clean")
    return 0


if __name__ == "__main__":
    sys.exit(check(Path(__file__).resolve().parent.parent))
