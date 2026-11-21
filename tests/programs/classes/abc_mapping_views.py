# A typing.Mapping[str, int] base is collections.abc.Mapping's (the subscript types nothing): the
# keys(), items() and values() views of lib's port, KeysView and ItemsView with Set's operators
# and comparisons (with builtin sets too), ValuesView's containment
import typing


class Letters(typing.Mapping[str, int]):
    def __init__(self, n: int) -> None:
        self.n = n

    def __getitem__(self, k: str) -> int:
        if len(k) != 1 or not ("a" <= k < chr(ord("a") + self.n)):
            raise KeyError(k)
        return ord(k) - ord("a")

    def __iter__(self):
        return iter([chr(ord("a") + i) for i in range(self.n)])

    def __len__(self) -> int:
        return self.n


m = Letters(3)
k = m.keys()
print(sorted(m.items()), m == {"a": 0, "b": 1, "c": 2}, m == Letters(3), m != Letters(2), "c" in m, m.get("z", 9))
print(k == {"a", "b", "c"}, k <= {"a", "b", "c", "d"}, k < {"a"}, sorted(k & {"a", "z"}), sorted(k | {"z"}), sorted(k - {"a"}))
print(sorted(k ^ {"a", "q"}), k.isdisjoint(["x"]), k.isdisjoint(["c"]), len(k), "b" in k)
items = m.items()
print(sorted(items & {("a", 0), ("b", 3)}), ("b", 1) in items, ("b", 2) in items, ("x", 0) in items)
values = m.values()
print(2 in values, 7 in values, len(values), list(values))
print(type(k).__name__, type(items).__name__, type(values).__name__, type(k).__module__)
