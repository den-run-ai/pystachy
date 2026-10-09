# with-files closed by an exception that leaves the block: what was written is flushed and the
# file closed before the handler runs, also from a function the handler's try calls
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/out.txt"


def write_and_fail(path: str, n: int) -> None:
    with open(path, "w") as f:
        f.write(f"line {n}\n")
        if n > 0:
            raise ValueError(n)
        f.write("not failed\n")


for n in range(2):
    try:
        write_and_fail(p, n)
    except ValueError as e:
        print("failed", e)
    with open(p) as g:
        print(repr(g.read()))
try:
    with open(p, "a") as f:
        try:
            f.write("inner\n")
            raise KeyError("x")
        except KeyError:
            f.write("handled inside\n")
        print("closed inside?", f.closed)
        xs: list[int] = []
        xs.pop()
except IndexError as e:
    print("closed after:", f.closed, e)
with open(p) as g:
    print(repr(g.read()))
for i in range(3):
    with open(p, "w") as f:
        try:
            if i == 1:
                continue
            f.write(str(i))
        finally:
            print("finally", i, f.closed)
    print("after with", i, f.closed)
os.remove(p)
os.rmdir(d)
