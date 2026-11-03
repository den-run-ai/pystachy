# error: PurePosixPath.__init__() takes from 1 to 9 positional arguments but 10 were given
# A path's constructor takes at most eight segments (CPython prints a/b/c/d/e/f/g/h/i)
from pathlib import Path

print(Path("a", "b", "c", "d", "e", "f", "g", "h", "i"))
