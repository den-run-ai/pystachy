# error: 'pathlib.PurePosixPath' object has no method 'exists'
# Iterating over a Path's parents gives PurePath items, as one type (CPython prints True)
from pathlib import Path

for p in Path("/tmp/x").parents:
    print(p.exists())
