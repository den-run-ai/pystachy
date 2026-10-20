# __init__ that tests hasattr(self, "f"): where the test is true, f is assigned, so a field that
# __init__ makes only where hasattr finds it missing is assigned wherever it is read, also when
# __init__ runs again (as lib/collections' mappings keep their dicts). Fields that may still be
# read unassigned raise AttributeError, as in CPython: also through a def or lambda that takes
# self before the test, whether it reads the tested field or another one.
from typing import Callable


class Tally:
    def __init__(self, words: list[str]) -> None:
        if not hasattr(self, "counts"):
            self.counts: dict[str, int] = {}
        if hasattr(self, "runs"):
            self.runs += 1
        else:
            self.runs = 1
        for w in words:
            self.counts[w] = self.counts.get(w, 0) + 1

    def get(self, w: str) -> int:
        return self.counts.get(w, 0)


t = Tally(["a", "b", "a"])
print(t.get("a"), t.get("b"), t.runs)
t.__init__(["a", "c"])
print(t.get("a"), t.get("c"), t.runs, sorted(t.counts.items()))


class Maybe:
    def __init__(self, on: bool) -> None:
        self.fresh = not hasattr(self, "x")
        if on:
            self.x = 1

    def get(self) -> int:
        return self.x


m = Maybe(False)
print(m.fresh, hasattr(m, "x"))
try:
    print(m.get())
except AttributeError as e:
    print("AttributeError:", e)
m.__init__(True)
print(m.fresh, m.get())
m.__init__(False)
print(m.fresh, m.get())


def peek(o: "Late") -> bool:
    return hasattr(o, "y")


class Late:
    def __init__(self) -> None:
        if not hasattr(self, "x"):
            self.x = 1
        print("y before:", peek(self))
        self.y = 2


lt = Late()
print(lt.x, lt.y, peek(lt))
lt.__init__()
print(lt.x + lt.y)


class Sized:
    def __init__(self) -> None:
        def size() -> int:
            return len(self.items)

        if not hasattr(self, "items"):
            try:
                print("size", size())
            except AttributeError as e:
                print("AttributeError:", e)
            self.items: list[str] = []
        self.items.append("a")
        print("size", size())


sz = Sized()
sz.__init__()
print(len(sz.items))


class Peeked:
    def __init__(self) -> None:
        peek: Callable[[], int] = lambda: len(self.y)
        first: Callable[[], int] = lambda: self.x
        if not hasattr(self, "x"):
            try:
                print("first", first())
            except AttributeError as e:
                print("AttributeError:", e)
            self.x = 1
        try:
            print("peek", peek())
        except AttributeError as e:
            print("AttributeError:", e)
        self.y: list[int] = [1]

    def get(self) -> int:
        return self.x + len(self.y)


pk = Peeked()
print(pk.get())
pk.__init__()
print(pk.get())
