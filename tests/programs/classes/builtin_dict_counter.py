# A Counter core, as collections.Counter is one: __missing__ returns 0, so c[k] += 1 counts a new
# key, while get(), in and pop() never call it; most_common() sorts the items.

class Counter(dict[str, int]):
    def __missing__(self, key: str) -> int:
        return 0

    def count_all(self, words: list[str]) -> None:
        for w in words:
            self[w] += 1

    def most_common(self, n: int) -> list[tuple[str, int]]:
        return sorted(self.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def total(self) -> int:
        return sum(self.values())


c = Counter()
c.count_all("the cat and the hat and the bat".split())
print(c["the"], c["dog"], len(c), "dog" in c, c.get("dog"), c.most_common(2), c.total())
c["dog"] += 5
c["cat"] -= 1
print(c["dog"], c["cat"], c.most_common(3), sorted(c), c == {"the": 3, "cat": 0, "and": 2, "hat": 1, "bat": 1, "dog": 5})
