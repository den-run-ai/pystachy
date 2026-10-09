# try statements inside finally blocks (compiled once for each way out), a return from an except
# clause inside a with block inside a loop, an exception from a template
import os
import tempfile


def tidy(n: int) -> list[str]:
    log: list[str] = []
    for i in range(n):
        try:
            if i == 1:
                return log
            log.append(f"body {i}")
        finally:
            try:
                if i == 0:
                    raise KeyError(i)
                log.append(f"finally {i}")
            except KeyError as e:
                log.append(f"finally caught {e}")
            finally:
                log.append(f"inner finally {i}")
    return log


def first_line(path: str, words: list[str]) -> str:
    for w in words:
        with open(path) as f:
            try:
                n = int(w)
            except ValueError as e:
                return f"{w!r} is no number, file closed: {f.closed}"
            print(n, f.readline().strip())
    return "all numbers"


def pick(xs, i):
    return xs[i]


def picks() -> None:
    for i in [0, 5]:
        try:
            print(pick([1, 2, 3], i), pick(["a", "b"], i))
        except IndexError as e:
            print("template raised:", e)
        except KeyError as e:
            print("not this", e)


print(tidy(3))
d = tempfile.mkdtemp()
p = d + "/f.txt"
with open(p, "w") as g:
    g.write("one\ntwo\n")
print(first_line(p, ["1", "2", "x", "3"]))
picks()
os.remove(p)
os.rmdir(d)
