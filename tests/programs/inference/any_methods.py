# typing.Any in the annotations of methods that may be templates: their other parameters but self
# or cls, and their returns, are typed by each call, as unannotated ones are; also a static and a
# class method's, the special methods that a call compiles as any other (__getitem__, __contains__,
# __eq__, __call__, a with statement's __enter__ and __exit__) and a generator's Iterator[Any]
from collections.abc import Iterator
from typing import Any


class Bag:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def __getitem__(self, key: Any) -> Any:
        return self.items[key]

    def __contains__(self, item: Any) -> bool:
        return item in self.items

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Bag) and other.items == self.items

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return len(args) + len(kwargs)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> None:
        print("exit", len(args), args[1] is None)

    @staticmethod
    def show(x: Any) -> str:
        return f"[{x}]"

    @classmethod
    def make(cls, x: Any) -> "Bag":
        return cls([len(x)])

    def merge(self, other: Any) -> Any:
        return self.items + other.items

    def pairs(self, fill: Any) -> Iterator[Any]:
        for x in self.items:
            yield (x, fill)


class Ctx:
    def __enter__(self) -> "Ctx":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        print("exit", exc_type is None, exc)
        return True


b = Bag([1, 2, 3])
print(b[0], b[2], 2 in b, 9 in b, b == Bag([1, 2, 3]), b == 4, b != "x")
print(b(1, "a", k=2), Bag.show(5), Bag.show("s"), Bag.make("xy").items, b.merge(Bag([4])))
print(list(b.pairs("f")), list(Bag([7]).pairs(None)))
with b as w:
    print("in", w.items)
with Ctx():
    print("body")
with Ctx():
    raise ValueError("boom")
print("after")
