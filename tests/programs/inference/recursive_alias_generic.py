# A generic recursive alias names one graph per type arguments: Value[float] and Value[bool]
# are two types, and Value[T] is the graph of what T is bound to.
from typing import Callable

type Value[F] = int | str | F | list[Value[F]] | dict[str, Value[F]]
type Two[F, G] = F | G | list[Two[F, G]]
type Tree[T] = T | list[Tree[T]]


def build(texts: list[str], parse: Callable[[str], float]) -> Value[float]:
    out: list[Value[float]] = []
    for s in texts:
        if s.isdigit():
            out.append(int(s))
        elif "." in s:
            out.append(parse(s))
        else:
            out.append(s)
    return {"items": out, "n": len(out)}


def total(v: Value[float]) -> float:
    if isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        return sum([total(x) for x in v])
    if isinstance(v, dict):
        return sum([total(x) for x in v.values()])
    return 0.0


def flags(v: Value[bool]) -> int:
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, list):
        return sum([flags(x) for x in v])
    if isinstance(v, dict):
        return sum([flags(x) for x in v.values()])
    return 0


def count(v: Two[int, str]) -> int:
    if isinstance(v, list):
        return sum([count(x) for x in v])
    return 1


def holes(v: Value[int | None]) -> int:
    if v is None:
        return 1
    if isinstance(v, list):
        return sum([holes(x) for x in v])
    return 0


def width[T](v: Value[T], leaf: T) -> int:
    if isinstance(v, list):
        return len(v)
    return 0


def use(value: Tree[int]) -> None:
    print(value)


class Holder[T]:
    def __init__(self, leaf: T) -> None:
        self.leaf = leaf
        self.doc: Value[T] = [leaf, 1, "one", {"k": [leaf]}]

    def show(self) -> str:
        return str(self.doc)


def main() -> None:
    a = build(["1", "2.5", "x"], float)
    print(a, total(a))
    v: Value[float] = [1, "a", 2.5, {"k": [3.5]}]
    print(v, total(v), v == [1, "a", 2.5, {"k": [3.5]}], width(v, 0.5))
    w: Value[bool] = {"on": True, "more": [False, True, 7, "s"]}
    print(w, flags(w))
    print(count([1, "a", [2, "b"]]), holes([1, None, [2, None]]))
    print(Holder(2.5).show(), Holder(True).show())
    use(1)
    use([1, [2, [3]]])


main()
