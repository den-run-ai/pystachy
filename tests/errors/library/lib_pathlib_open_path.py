# error: expected str, got PosixPath
# open() takes a str: str(path) or path.open() opens a path (CPython opens /dev/null)
from pathlib import Path

with open(Path("/dev/null")) as f:
    print(f.read())
