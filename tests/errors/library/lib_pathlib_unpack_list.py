# error: unpacking a list[str] into the arguments of pathlib.PosixPath() is not supported (a tuple's items are)
# A path's constructor takes its segments as parameters (CPython prints a/b)
from pathlib import Path

parts = ["a", "b"]
print(Path(*parts))
