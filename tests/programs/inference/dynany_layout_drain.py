# pystachy: dynamic-any
# A list of Any containers holds them as boxes (dynany_layout), also where it is built from an
# iterator object's items: list(it), [*it], xs.extend(it) and sorted(it) box each item as they take
# it, so the list holds the iterator's own containers (#821: Codex's finding).
from typing import Any


class Records:
    def __init__(self, n: int) -> None:
        self.n = n
        self.made: list[Any] = []

    def __iter__(self) -> "Records":
        return self

    def __next__(self) -> dict[str, Any]:
        if len(self.made) >= self.n:
            raise StopIteration
        r: dict[str, Any] = {"id": len(self.made), "tags": ["t" + str(len(self.made))]}
        self.made.append(r)
        return r


class Rows:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Rows":
        return self

    def __next__(self) -> list[Any]:
        if self.i >= 3:
            raise StopIteration
        self.i += 1
        return [3 - self.i, "row"]


it = Records(2)
xs = list(it)
print(xs, xs[1]["tags"][0])
print(xs[0] is it.made[0], xs[1] is it.made[1])
xs[0]["id"] = 10
print(it.made[0])
a: Any = xs
print(a[1]["id"], len(a))

it2 = Records(3)
ys = [*it2]
print(ys[2], ys[2] is it2.made[2])

zs: list[Any] = [{"id": -1}]
it3 = Records(2)
zs.extend(it3)
print(zs, zs[2] is it3.made[1])

print(sorted(Rows()), list(Rows())[0][1])
