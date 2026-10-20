# A def or lambda in __init__ that takes self can run before __init__ assigns a field it reads,
# there or later, from wherever it was passed: the read raises AttributeError, as in CPython.
# Fields assigned before the function is defined are read as usual.
from typing import Callable


def attempt(f: Callable[[], str]) -> None:
    try:
        print(f())
    except AttributeError as e:
        print("AttributeError:", e)


class Peek:
    def __init__(self) -> None:
        self.base = 10

        def size() -> int:
            return self.base + len(self.items)

        try:
            print("size", size())
        except AttributeError as e:
            print("AttributeError:", e)
        self.items: list[int] = [1, 2]
        print("size", size())

    def n(self) -> int:
        return len(self.items)


print(Peek().n())


class Hook:
    def __init__(self, hooks: list[Callable[[], str]]) -> None:
        hooks.append(lambda: self.name.upper())
        for h in hooks:
            attempt(h)
        self.name = "hook"


hooks: list[Callable[[], str]] = []
Hook(hooks)
print(hooks[0]())


class Nested:
    def __init__(self) -> None:
        def outer() -> str:
            def inner() -> str:
                return self.tag

            return inner()

        twice: Callable[[], str] = lambda: (lambda: self.tag * 2)()
        attempt(outer)
        attempt(twice)
        self.tag = "t"
        print(outer(), twice())


Nested()


class Ranked:
    def __init__(self, xs: list[str]) -> None:
        try:
            print(sorted(xs, key=lambda x: self.weight[x]))
        except AttributeError as e:
            print("AttributeError:", e)
        self.weight: dict[str, int] = {"a": 2, "b": 1}
        print(sorted(xs, key=lambda x: self.weight[x]))


Ranked(["a", "b"])
