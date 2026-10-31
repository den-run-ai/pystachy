# With-file unwind actions root native files and close them deterministically.
# Recursion bookkeeping can be elided in scalar helpers without relying on GC
# to flush their output, including return, break, continue and exceptional exits.
import os
import sys
from typing import TextIO


held: list[TextIO] = []
path = "rt_recursion_scoped_files.txt"


def scalar(n: int) -> int:
    return n + 1


def descend(n: int) -> int:
    if n == 0:
        return scalar(1)
    return descend(n - 1)


def callback(mode: int) -> int:
    if mode == 2:
        raise ValueError("callback")
    if mode == 3:
        return descend(200)
    return scalar(mode)


def write(mode: int) -> int:
    with open(path, "w") as stream:
        held.append(stream)
        stream.write(str(scalar(mode)))
        if mode == 1:
            return scalar(mode)
        stream.write(str(callback(mode)))
    return scalar(mode)


saved = sys.getrecursionlimit()
sys.setrecursionlimit(80)
for case in range(4):
    try:
        print("result", write(case))
    except ValueError:
        print("value error")
    except RecursionError:
        print("recursion error")
    with open(path) as reader:
        print(case, held[-1].closed, reader.read())
    os.remove(path)
print("recovered", descend(4))
sys.setrecursionlimit(saved)

for case in range(3):
    with open(path, "w") as stream:
        held.append(stream)
        stream.write(str(scalar(case)))
        if case == 0:
            continue
        break
with open(path) as reader:
    print("loop", all(stream.closed for stream in held), reader.read())
os.remove(path)

try:
    with open(path, "w") as outer, open(path + ".inner", "w") as inner:
        held.append(outer)
        held.append(inner)
        outer.write("outer")
        inner.write("inner")
        callback(2)
except ValueError:
    print("nested", held[-2].closed, held[-1].closed)
for suffix in ["", ".inner"]:
    with open(path + suffix) as reader:
        print(reader.read())
    os.remove(path + suffix)
