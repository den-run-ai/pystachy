# A generator whose send type is a file: next() sends None, send() a file.
import os
import tempfile
from collections.abc import Generator
from typing import TextIO


def sink() -> Generator[int, TextIO, None]:
    count = 0
    while True:
        out = yield count
        if out is None:
            print("no file")
            continue
        out.write("line " + str(count) + "\n")
        count += 1


d = tempfile.mkdtemp()
path = os.path.join(d, "out.txt")
g = sink()
print(next(g))
with open(path, "w") as f:
    print(g.send(f), g.send(f))
    print(next(g))
with open(path) as f:
    print(f.read().split("\n"))
for v in sink():
    print(v)
    if v == 0:
        break
