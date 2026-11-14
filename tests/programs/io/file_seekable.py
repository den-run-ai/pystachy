# file.seekable(), and explicit __enter__() and __exit__() calls of a file.
import os
import tempfile


def main() -> None:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "a.txt")
    with open(p, "w") as f:
        f.write("x")
        print("w:", f.seekable())
    f = open(p)
    print("r:", f.seekable())
    f.close()
    try:
        print(f.seekable())
    except ValueError as e:
        print("closed:", e)


def protocol() -> None:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "b.txt")
    f = open(p, "w")
    g = f.__enter__()
    g.write("text")
    print(g is f, f.__exit__(None, None, None), f.closed)
    try:
        f.__enter__()
    except ValueError as e:
        print("closed:", e)
    with open(p) as r:
        print(r.read())


main()
protocol()
