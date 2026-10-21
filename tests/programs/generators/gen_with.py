# A generator suspended in a with block (#490): its file stays open while it is suspended, and
# its consumer's own with blocks and try statements in between do not close it; a loop that owns
# it closes the file as it is left (break, return, an exception), after the generator's finally
# blocks inside the with block have run.
import os
import tempfile
from collections.abc import Iterator

d = tempfile.mkdtemp()
path = os.path.join(d, "lines.txt")
other = os.path.join(d, "other.txt")
with open(path, "w") as f:
    f.write("one\ntwo\nthree\nfour\n")
with open(other, "w") as f:
    f.write("x\ny\n")


def lines(p: str) -> Iterator[str]:
    with open(p) as fh:
        try:
            for line in fh:
                yield line.strip()
        finally:
            print("  finally, file closed:", fh.closed)
    print("  after with")


for s in lines(path):
    print("line", s)
for s in lines(path):
    print("first", s)
    break
try:
    for s in lines(path):
        with open(other) as g:
            print("inner file", g.readline().strip())
        try:
            raise KeyError("caught in the body")
        except KeyError:
            print("handled", s)
        if s == "three":
            raise ValueError("leave")
except ValueError as e:
    print("caught", e)


def count_until(p: str, stop: str) -> int:
    n = 0
    for s in lines(p):
        n += 1
        if s == stop:
            return n
    return -1


print(count_until(path, "two"))
it = lines(path)
for s in it:
    print("partial", s)
    break
try:
    raise RuntimeError("consumer's own")
except RuntimeError as e:
    print("consumer caught", e)
for s in it:
    print("resumed", s)
os.remove(path)
os.remove(other)
os.rmdir(d)
