# ThreadPoolExecutor.submit(): the forms of a call (a function with positional and keyword
# arguments, a lambda, a bound method, a builtin, a method of str) and the types of its result,
# which is its future's: an int, a str, an object, an optional str, a tuple, a list and None.
# Each state is read after result(), when a pool's worker has finished the call too
from concurrent.futures import Future, ThreadPoolExecutor


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)

    def scaled(self, k: int) -> "Point":
        return Point(self.x * k, self.y * k)


def square(n: int) -> int:
    return n * n


def join(a: str, b: str, sep: str = "-") -> str:
    return a + sep + b


def find(words: list[str], w: str) -> str | None:
    if w in words:
        return w
    return None


def note(log: list[str], w: str) -> None:
    log.append(w)


def pair(n: int) -> tuple[int, str]:
    return n, str(n)


def halves(n: int) -> list[float]:
    return [n / 2, n / 4]


executor = ThreadPoolExecutor(max_workers=2)
f1 = executor.submit(square, 7)
print(f1.result(), f1.done(), f1.running(), f1.cancelled(), f1.cancel(), f1.exception())
f2 = executor.submit(join, "a", "b")
f3 = executor.submit(join, "a", "b", sep="+")
f4 = executor.submit(join, b="y", a="x")
print(f2.result(), f3.result(), f4.result())
f5 = executor.submit(lambda: 42)
f6 = executor.submit(lambda a, b: a * b, 6, 7)
print(f5.result() + f6.result())
p = Point(3, -4)
f7 = executor.submit(p.norm1)
f8 = executor.submit(p.scaled, 2)
print(f7.result(), f8.result().x, f8.result().y, f8.result() is f8.result())
words = ["x", "y"]
f9 = executor.submit(find, words, "y")
f10 = executor.submit(find, words, "z")
print(f9.result(), f10.result())
log: list[str] = []
f11 = executor.submit(note, log, "w")
print(f11.result(), f11.done(), log)
f12 = executor.submit(pair, 5)
n, s = f12.result()
print(n, s)
f13 = executor.submit(halves, 3)
print(f13.result())
f14 = executor.submit(len, "four")
f15 = executor.submit(str.upper, "abc")
print(f14.result(), f15.result())
print(f1.result(timeout=1), f1.result(0), f1.exception(timeout=0.5))
executor.shutdown()
print(isinstance(f1, Future), isinstance(f11, Future), f1 == f1, f1 == f5, f1 is not f5)
r = repr(f1)
print(r[:11], r[r.index(" state="):])
r = repr(f11)
print(r[r.index(" state="):], repr(f2)[-13:], repr(f8)[-15:])
