import sys


def letters(text: str) -> tuple[str, ...]:
    return tuple(set(text))


def numbers(limit: int) -> tuple[int, ...]:
    seen: set[int] = set()
    for value in range(limit):
        seen.add(value * 7 % 5)
    return tuple(seen)


def keys(table: dict[str, int]) -> tuple[str, ...]:
    return tuple(table)


text = sys.argv[1] if len(sys.argv) > 1 else "abracadabra"
unique = letters(text)
print(len(unique), sorted(unique), tuple(sorted(set(text))) == tuple(sorted(unique)))
print(numbers(12), tuple(set([3, 1, 2])), tuple(frozenset([5, 4])))
print(keys({"b": 1, "a": 2}), tuple({1: "x", 0: "y"}), tuple({"only": 1}.keys()))
empty: set[str] = set()
print(tuple(empty), tuple(set("x")) == ("x",), len(tuple({"p": 0, "q": 0})))
pairs = tuple({"a": (1, 2), "b": (3, 4)})
print(len(pairs), sorted(tuple({"b", "a", "c"})), tuple(set(range(3))))
