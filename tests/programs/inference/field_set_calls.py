# A field stored from set(xs) or frozenset(xs) is a set of the items of xs (of a list, tuple,
# string, range or set, or of a dict's keys), as mypyc's RUnion stores self.items_set =
# frozenset(items).
class RType:
    def __init__(self, name: str) -> None:
        self.name = name


class RUnion:
    def __init__(self, items: list[RType]) -> None:
        self.items = items
        self.items_set = frozenset(items)


class Sets:
    def __init__(self, words: list[str], pair: tuple[int, int], text: str, n: int, counts: dict[str, int], seen: set[str]) -> None:
        self.words = set(words)
        self.pair = frozenset(pair)
        self.chars = set(text)
        self.nums = frozenset(range(n))
        self.keys = set(counts)
        self.copy = set(seen)
        self.frozen = frozenset(self.words)


a = RType("int")
u = RUnion([a, RType("str"), a])
print(len(u.items_set), a in u.items_set, RType("int") in u.items_set)
seen = {"q"}
s = Sets(["b", "a", "b"], (2, 1), "hello", 3, {"x": 1, "y": 2}, seen)
print(sorted(s.words), sorted(s.pair), sorted(s.chars), sorted(s.nums), sorted(s.keys), s.copy)
s.words.add("c")
seen.add("r")
print(sorted(s.words), sorted(s.frozen), s.copy, s.frozen == frozenset(["a", "b"]))
